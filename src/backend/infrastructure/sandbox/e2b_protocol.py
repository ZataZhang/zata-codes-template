"""阿里云 FC 云沙箱 E2B 兼容协议底座。

云沙箱对外暴露 E2B 协议,但官方 SDK 没有任何可用版本能对接该端点(新版走未实现的
``/v2/sandboxes``、中间版本把沙箱标识拼成 ``{id}-{accountID}`` 导致执行通道全程
404、旧版走不通的传输方式),因此在基础设施层内按协议直接实现。

本模块只放三样东西:错误类型、跨平面共用的值对象、Connect 协议分帧编解码。控制面
与执行通道各自成模块(``e2b_control_plane`` / ``e2b_execution_channel``),共享这里
的取值约定,但互不依赖。

分帧与错误映射都是显式的:畸形帧、超长帧与错误状态一律抛
:class:`E2bProtocolError`,不做"静默返回空结果"。上层据此把 Run 判为失败,而不是
留下"空产物但状态成功"的假象。
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

CONNECT_DATA_FLAG: int = 0x00
"""Connect 流式响应里携带事件载荷的数据帧标记。"""

CONNECT_END_STREAM_FLAG: int = 0x02
"""Connect 流式响应里终止帧的标记;其载荷为 ``{}`` 或错误对象。"""

ENVD_HTTPS_PORT: int = 49983
"""envd 网关在沙箱域名上暴露的 HTTPS 端口。"""

_CONNECT_FRAME_HEADER_BYTES = 5
_CONNECT_MAX_FRAME_BYTES = 8 * 1024 * 1024


class E2bProtocolError(RuntimeError):
    """云沙箱协议或传输层错误。

    抛出即表示"这次操作没有拿到可信结果",调用方不得把它当作命令执行失败(退出码)
    处理,而应让 Run 以失败收尾。
    """


class E2bSandboxNotFoundError(E2bProtocolError):
    """目标沙箱已过期、被回收或从未存在。"""


@dataclass(frozen=True)
class E2bEndpointConfig:
    """连接云沙箱所需的端点与默认参数。

    这里持有 API 密钥本身,但绝不写日志、证据或异常消息:该对象只在
    ``infrastructure`` 层内传递。

    Attributes:
        api_url (str): 控制面基地址。
        api_key (str): 控制面凭据;该字段不进 ``repr``,避免对象被随手打进日志。
        domain (str): envd 网关域名;为空时以创建响应中的 ``domain`` 为准。
        template_id (str): 平台自建执行模板标识。
        timeout_seconds (int): 新建沙箱的存活窗口秒数。
        username (str): 执行通道文件读写使用的沙箱用户名。
        allow_internet_access (bool): 是否允许沙箱出网;默认关闭。
    """

    api_url: str
    api_key: str = field(repr=False)
    domain: str
    template_id: str
    timeout_seconds: int
    username: str
    allow_internet_access: bool


@dataclass(frozen=True)
class E2bSandboxHandle:
    """一个已创建云沙箱的访问句柄。

    Attributes:
        sandbox_id (str): 控制面返回的裸沙箱标识;envd 网关只认这个裸值。
        envd_base_url (str): 该沙箱执行通道的基地址。
        access_token (str): 执行通道访问令牌;该字段不进 ``repr``。
        timeout_seconds (int): 创建时生效的存活窗口秒数。
    """

    sandbox_id: str
    envd_base_url: str
    access_token: str = field(repr=False)
    timeout_seconds: int


@dataclass(frozen=True)
class E2bExecOutcome:
    """一次云沙箱命令执行的解码结果。

    Attributes:
        stdout_bytes (bytes): 标准输出。
        stderr_bytes (bytes): 标准错误。
        exit_code (int): 命令退出码;非 0 表示命令自身失败。
        truncated (bool): 输出是否因超过上限被丢弃后半段。
    """

    stdout_bytes: bytes
    stderr_bytes: bytes
    exit_code: int
    truncated: bool


def encode_connect_frame(payload: bytes) -> bytes:
    """把一段 JSON 载荷编码为 Connect 流式请求帧。

    Args:
        payload (bytes): 已序列化的 JSON 载荷。

    Returns:
        bytes: 5 字节头(1 字节 flags + 4 字节大端长度)加载荷。
    """
    return bytes([CONNECT_DATA_FLAG]) + struct.pack(">I", len(payload)) + payload


def decode_connect_frames(response_body: bytes) -> list[tuple[int, bytes]]:
    """把 Connect 流式响应体解码为 (flags, 载荷) 列表。

    整体解码而不是逐步产出:响应被截断或长度前缀自相矛盾时必须立刻失败,不能把
    "读到的部分帧"当成完整结果交给上层。

    Args:
        response_body (bytes): 执行通道返回的完整响应体。

    Returns:
        list[tuple[int, bytes]]: 按出现顺序排列的帧。空响应体返回空列表。

    Raises:
        E2bProtocolError: 长度前缀越界、帧声明长度超过剩余字节,或单帧长度异常。
    """
    decoded_frames: list[tuple[int, bytes]] = []
    frame_offset = 0
    while frame_offset < len(response_body):
        if len(response_body) - frame_offset < _CONNECT_FRAME_HEADER_BYTES:
            raise E2bProtocolError("云沙箱执行通道返回了不完整的帧头")
        frame_flag = response_body[frame_offset]
        frame_length = struct.unpack(
            ">I", response_body[frame_offset + 1 : frame_offset + _CONNECT_FRAME_HEADER_BYTES]
        )[0]
        if frame_length > _CONNECT_MAX_FRAME_BYTES:
            raise E2bProtocolError(f"云沙箱执行通道声明了异常帧长度: {frame_length}")
        frame_end_offset = frame_offset + _CONNECT_FRAME_HEADER_BYTES + frame_length
        if frame_end_offset > len(response_body):
            raise E2bProtocolError("云沙箱执行通道返回的帧长度超出响应体")
        decoded_frames.append((frame_flag, response_body[frame_offset + 5 : frame_end_offset]))
        frame_offset = frame_end_offset
    return decoded_frames


def build_envd_base_url(*, sandbox_id: str, domain: str) -> str:
    """按裸沙箱标识与网关域名拼出执行通道基地址。

    Args:
        sandbox_id (str): 控制面返回的裸沙箱标识。
        domain (str): envd 网关域名。

    Returns:
        str: 形如 ``https://49983-<sandbox_id>.<domain>`` 的基地址。

    Raises:
        ValueError: 沙箱标识或域名为空。
    """
    if not sandbox_id or not domain:
        raise ValueError("云沙箱标识与网关域名都不能为空")
    return f"https://{ENVD_HTTPS_PORT}-{sandbox_id}.{domain}"


def decode_json_object(*, response_text: str, action: str) -> dict[str, object]:
    """把响应体解析为 JSON 对象。

    Args:
        response_text (str): 响应体文本。
        action (str): 操作名,用于错误消息定位。

    Returns:
        dict[str, object]: 解析出的 JSON 对象。

    Raises:
        E2bProtocolError: 响应体不是 JSON 对象。
    """
    try:
        decoded_payload = json.loads(response_text)
    except json.JSONDecodeError as decode_error:
        raise E2bProtocolError(
            f"云沙箱{action}返回了非 JSON 响应: {decode_error}"
        ) from decode_error
    if not isinstance(decoded_payload, dict):
        raise E2bProtocolError(f"云沙箱{action}返回的 JSON 不是对象")
    return decoded_payload


def decode_json_array(*, response_text: str, action: str) -> list[object]:
    """把响应体解析为 JSON 数组。

    控制面的列举接口返回的是**裸数组**而不是包在对象里的字段,和创建接口的形状不同;
    多一层 ``{"sandboxes": [...]}`` 的假设会让列举恒为空,而"没有孤儿沙箱"这个结论
    恰恰不能由解析失败伪造。

    Args:
        response_text (str): 响应体文本。
        action (str): 操作名,用于错误消息定位。

    Returns:
        list[object]: 解析出的数组元素。

    Raises:
        E2bProtocolError: 响应体不是 JSON 数组。
    """
    try:
        decoded_payload = json.loads(response_text)
    except json.JSONDecodeError as decode_error:
        raise E2bProtocolError(
            f"云沙箱{action}返回了非 JSON 响应: {decode_error}"
        ) from decode_error
    if not isinstance(decoded_payload, list):
        raise E2bProtocolError(f"云沙箱{action}返回的 JSON 不是数组")
    return decoded_payload


def build_status_error(
    *,
    action: str,
    status_code: int,
    response_body: str,
    missing_sandbox_on_404: bool = True,
) -> E2bProtocolError:
    """把非成功状态码映射为明确的协议异常。

    404 是否等同于"沙箱已被回收"取决于调用方:控制面与命令执行通道的 404 只可能
    来自沙箱本身;文件读写通道的 404 还可能是"这个文件不存在",误判成沙箱消失会
    让排障方向完全跑偏。

    Args:
        action (str): 操作名。
        status_code (int): HTTP 状态码。
        response_body (str): 响应体文本,只取前若干字节避免把大响应体写进日志。
        missing_sandbox_on_404 (bool): 404 是否映射为沙箱不存在。

    Returns:
        E2bProtocolError: 可直接抛出的异常实例。
    """
    diagnostic_body = response_body.strip()[:200]
    if status_code == 404 and missing_sandbox_on_404:
        return E2bSandboxNotFoundError(
            f"云沙箱{action}失败: 沙箱不存在或已被回收(404) {diagnostic_body}"
        )
    return E2bProtocolError(f"云沙箱{action}失败: HTTP {status_code} {diagnostic_body}")


def build_transport_error(*, action: str, transport_error: Exception) -> E2bProtocolError:
    """把传输层异常映射为协议异常。

    Args:
        action (str): 操作名。
        transport_error (Exception): 底层传输异常。

    Returns:
        E2bProtocolError: 可直接抛出的异常实例。
    """
    return E2bProtocolError(
        f"云沙箱{action}传输失败: {type(transport_error).__name__}: {transport_error}"
    )


__all__ = [
    "CONNECT_DATA_FLAG",
    "CONNECT_END_STREAM_FLAG",
    "ENVD_HTTPS_PORT",
    "E2bEndpointConfig",
    "E2bExecOutcome",
    "E2bProtocolError",
    "E2bSandboxHandle",
    "E2bSandboxNotFoundError",
    "build_envd_base_url",
    "build_status_error",
    "build_transport_error",
    "decode_connect_frames",
    "decode_json_array",
    "decode_json_object",
    "encode_connect_frame",
]
