"""云沙箱协议编解码、错误映射与后端装配测试(无云)。

覆盖控制面响应解析、执行通道分帧解码、文件读写与超时/截断语义;畸形帧与错误
状态码必须映射为明确异常,不做静默空结果。

运行时行为用 ``tests/backend/cloud_sandbox_test_support.py`` 的内存替身演练;真实云
沙箱验收见 ``tests/backend/test_cloud_sandbox_e2b_live.py``。
"""

from __future__ import annotations

import json
import struct
import subprocess
from pathlib import Path

import httpx
import pytest

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxFileWrite,
)
from backend.infrastructure.config.sandbox_settings import (
    SandboxAgentConfig,
    SandboxAgentConfigError,
    load_sandbox_agent_config,
)
from backend.infrastructure.sandbox.e2b_control_plane import E2bControlPlane
from backend.infrastructure.sandbox.e2b_execution_channel import E2bExecutionChannel
from backend.infrastructure.sandbox.e2b_protocol import (
    CONNECT_END_STREAM_FLAG,
    E2bEndpointConfig,
    E2bProtocolError,
    E2bSandboxHandle,
    E2bSandboxNotFoundError,
    build_status_error,
    decode_connect_frames,
    decode_json_array,
    decode_json_object,
    encode_connect_frame,
)
from backend.infrastructure.sandbox.e2b_provider import (
    _IDENTITY_LOST_EXIT_CODE,
    _IDENTITY_LOST_MARKER,
    E2bSandboxProvider,
    build_identity_guarded_command,
)
from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy
from backend.infrastructure.sandbox.sandbox_rules import MAX_SANDBOX_OUTPUT_BYTES
from tests.backend.cloud_sandbox_test_support import (
    DEFAULT_ACCESS_TOKEN,
    DEFAULT_DOMAIN,
    FakeCloudSandboxService,
    build_error_end_stream_body,
    build_exec_response_body,
)

_ENDPOINT_CONFIG = E2bEndpointConfig(
    api_url="https://api.sandbox.example.test",
    api_key="e2b_test_key_not_a_real_secret",
    domain="",
    template_id="zata-sandbox",
    timeout_seconds=600,
    username="user",
    allow_internet_access=False,
)

_SKILL_ASSET_PATH = f"{SANDBOX_SKILL_RUNTIME_ROOT}/excel-skill/scripts/compare.py"
_FIRST_STAGED_SKILL_ASSET_PATH = f"{SANDBOX_SKILL_RUNTIME_ROOT}/first/scripts/compare.py"


def _build_provider(service: FakeCloudSandboxService) -> E2bSandboxProvider:
    """用内存替身构造云沙箱 provider。"""
    return E2bSandboxProvider(
        config=_ENDPOINT_CONFIG,
        command_timeout_seconds=120,
        http_client=service.create_client(),
    )


def _build_isolated_channel(response_body: bytes, *, status_code: int = 200) -> E2bExecutionChannel:
    """构造只回放固定响应体的执行通道,用于演练畸变响应。"""
    response = httpx.Response(
        status_code,
        content=response_body,
        headers={"Content-Type": "application/connect+json"},
    )
    sandbox_handle = E2bSandboxHandle(
        sandbox_id="sb-isolated",
        envd_base_url=f"https://49983-sb-isolated.{DEFAULT_DOMAIN}",
        access_token=DEFAULT_ACCESS_TOKEN,
        timeout_seconds=60,
    )
    return E2bExecutionChannel(
        handle=sandbox_handle,
        username="user",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda _request: response)),
    )


def _build_isolated_control_plane(response: httpx.Response) -> E2bControlPlane:
    """构造只回放固定响应的控制面客户端,用于演练畸变响应。"""
    return E2bControlPlane(
        config=_ENDPOINT_CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda _request: response)),
    )


# ---------------------------------------------------------------------------
# 分帧编解码
# ---------------------------------------------------------------------------


def test_connect_frames_round_trip_preserves_flags_and_payloads() -> None:
    """编码后再解码得到同一组 (flags, 载荷)。"""
    encoded_body = (
        encode_connect_frame(b'{"event":{"start":{"pid":1}}}')
        + encode_connect_frame(b'{"event":{"end":{"exitCode":0}}}')
        + bytes([CONNECT_END_STREAM_FLAG])
        + struct.pack(">I", 2)
        + b"{}"
    )

    decoded_frames = decode_connect_frames(encoded_body)

    assert [frame_flag for frame_flag, _payload in decoded_frames] == [0x00, 0x00, 0x02]
    assert decoded_frames[-1][1] == b"{}"


def test_connect_frames_reject_truncated_header() -> None:
    """只有半截帧头时必须失败,不能把残缺数据当结果。"""
    with pytest.raises(E2bProtocolError, match="不完整的帧头"):
        decode_connect_frames(b"\x00\x00\x00")


def test_connect_frames_reject_length_beyond_body() -> None:
    """帧声明长度超出响应体时必须失败。"""
    oversized_frame = bytes([0x00]) + struct.pack(">I", 64) + b"short"

    with pytest.raises(E2bProtocolError, match="帧长度超出响应体"):
        decode_connect_frames(oversized_frame)


def test_connect_frames_reject_absurd_length() -> None:
    """荒谬的长度前缀必须在分配前被拒绝。"""
    absurd_frame = bytes([0x00]) + struct.pack(">I", 512 * 1024 * 1024) + b""

    with pytest.raises(E2bProtocolError, match="异常帧长度"):
        decode_connect_frames(absurd_frame)


def test_connect_frames_return_empty_for_empty_body() -> None:
    """空响应体解出零帧;是否可信由调用方按"缺少结束事件"判定。"""
    assert decode_connect_frames(b"") == []


# ---------------------------------------------------------------------------
# 身份自校验对命令体的透明度
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shell_command",
    [
        "echo hi # 未加引号的注释",
        "printf '%s\\n' <<'EOF'\nheredoc-body\nEOF",
        "echo before\n# 中间注释\necho after",
        "echo ok",
    ],
)
def test_identity_guard_keeps_command_bodies_intact(tmp_path: Path, shell_command: str) -> None:
    """带注释与 heredoc 的合法命令不得因身份自校验而变语法错误。

    回归用例:早先的实现把命令包进 ``{ ... ; }``,尾部的 ``; }`` 会落进注释作用域、
    或把 heredoc 终止行变成 ``EOF ; }``,使这些命令在 e2b 档报语法错误,而在 docker 档
    正常执行。这里直接把守卫字符串交给真实 ``/bin/sh`` 跑,因此检验的是 shell 语义
    而不是字符串形状。
    """
    identity_file_path = tmp_path / "identity"
    identity_file_path.write_text("expected-nonce", encoding="utf-8")
    guarded_command = build_identity_guarded_command(
        identity_path=str(identity_file_path),
        identity_nonce="expected-nonce",
        command=shell_command,
    )

    execution = subprocess.run(
        ["/bin/sh", "-lc", guarded_command], capture_output=True, text=True, check=False
    )

    assert execution.returncode == 0, execution.stderr
    assert _IDENTITY_LOST_MARKER not in execution.stdout


def test_identity_guard_blocks_command_when_identity_is_gone(tmp_path: Path) -> None:
    """身份标记不匹配时命令体根本不执行,并以固定退出码与标记收场。"""
    missing_identity_path = tmp_path / "missing-identity"
    guarded_command = build_identity_guarded_command(
        identity_path=str(missing_identity_path),
        identity_nonce="expected-nonce",
        command="echo should-not-run",
    )

    execution = subprocess.run(
        ["/bin/sh", "-lc", guarded_command], capture_output=True, text=True, check=False
    )

    assert execution.returncode == _IDENTITY_LOST_EXIT_CODE
    assert _IDENTITY_LOST_MARKER in execution.stdout
    assert "should-not-run" not in execution.stdout


def test_session_passes_command_body_to_sandbox_verbatim() -> None:
    """沙箱收到的命令体与调用方给的字符串逐字一致(只多了一行前置校验)。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")
    command_with_comment = "echo hi # 注释\ncat > /workspace/outputs/out.txt <<'EOF'\nbody\nEOF"

    sandbox_session.execute(command_with_comment, timeout_seconds=30)

    assert fake_service.executed_commands[-1] == command_with_comment


# ---------------------------------------------------------------------------
# 错误映射
# ---------------------------------------------------------------------------


def test_status_error_maps_404_to_missing_sandbox() -> None:
    """控制面/执行通道的 404 表示沙箱已被回收。"""
    mapped_error = build_status_error(
        action="执行命令", status_code=404, response_body="sandbox not found"
    )

    assert isinstance(mapped_error, E2bSandboxNotFoundError)


def test_status_error_keeps_404_as_plain_error_for_files() -> None:
    """文件通道的 404 只是"这个文件不存在",不能误报成沙箱消失。"""
    mapped_error = build_status_error(
        action="读取文件",
        status_code=404,
        response_body="file not found",
        missing_sandbox_on_404=False,
    )

    assert not isinstance(mapped_error, E2bSandboxNotFoundError)
    assert isinstance(mapped_error, E2bProtocolError)


def test_status_error_carries_status_and_truncated_body() -> None:
    """非成功状态码带上状态码与截断后的响应体,便于排障。"""
    mapped_error = build_status_error(action="创建沙箱", status_code=500, response_body="x" * 500)

    assert "HTTP 500" in str(mapped_error)
    assert len(str(mapped_error)) < 400


def test_decode_json_object_rejects_non_json_and_non_object() -> None:
    """非 JSON 与 JSON 数组都不是合法响应。"""
    with pytest.raises(E2bProtocolError, match="非 JSON"):
        decode_json_object(response_text="<html>", action="创建沙箱")
    with pytest.raises(E2bProtocolError, match="不是对象"):
        decode_json_object(response_text="[]", action="创建沙箱")


def test_decode_json_array_reads_bare_array_and_rejects_object() -> None:
    """列举接口返回裸数组;误按对象解析必须失败而不是当成空列表。"""
    assert decode_json_array(response_text='[{"sandboxID": "sb-1"}]', action="列举沙箱") == [
        {"sandboxID": "sb-1"}
    ]
    with pytest.raises(E2bProtocolError, match="不是数组"):
        decode_json_array(response_text='{"sandboxes": []}', action="列举沙箱")


def test_list_sandbox_ids_rejects_non_array_response() -> None:
    """控制面把列举响应写成对象时抛错,不能静默返回"没有孤儿沙箱"。"""
    control_plane = _build_isolated_control_plane(
        httpx.Response(200, json={"sandboxes": [{"sandboxID": "sb-1"}]})
    )

    with pytest.raises(E2bProtocolError, match="不是数组"):
        control_plane.list_sandbox_ids()


def test_list_sandbox_ids_reads_bare_array_response() -> None:
    """裸数组响应被解析为沙箱标识列表。"""
    control_plane = _build_isolated_control_plane(
        httpx.Response(200, json=[{"sandboxID": "sb-1"}, {"sandboxID": "sb-2"}, {"other": 1}])
    )

    assert control_plane.list_sandbox_ids() == ["sb-1", "sb-2"]


def test_exec_error_end_stream_raises_without_leaking_token() -> None:
    """终止帧带错误时抛出,且异常消息不携带访问令牌。"""
    execution_channel = _build_isolated_channel(
        build_error_end_stream_body(code="internal", message="boom")
    )

    with pytest.raises(E2bProtocolError, match="执行通道返回错误") as raised_error:
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )

    assert DEFAULT_ACCESS_TOKEN not in str(raised_error.value)


def test_exec_error_end_stream_maps_sandbox_not_found() -> None:
    """沙箱级错误码映射为"已被回收"。"""
    execution_channel = _build_isolated_channel(
        build_error_end_stream_body(code="not_found", message="sandbox gone")
    )

    with pytest.raises(E2bSandboxNotFoundError):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_exec_without_end_event_is_rejected() -> None:
    """没有结束事件时结果不可信,必须失败而不是返回空成功。"""
    execution_channel = _build_isolated_channel(
        encode_connect_frame(json.dumps({"event": {"start": {"pid": 1}}}).encode())
    )

    with pytest.raises(E2bProtocolError, match="没有返回命令结束事件"):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_exec_rejects_invalid_base64_output() -> None:
    """输出字段不是合法 base64 时不能当成空输出。"""
    broken_frame = encode_connect_frame(
        json.dumps({"event": {"data": {"stdout": "!!!not-base64!!!"}}}).encode()
    )
    execution_channel = _build_isolated_channel(broken_frame)

    with pytest.raises(E2bProtocolError, match="合法 base64"):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_exec_surfaces_http_status_as_protocol_error() -> None:
    """执行通道返回 502 时映射为协议异常。"""
    execution_channel = _build_isolated_channel(b"", status_code=502)

    with pytest.raises(E2bProtocolError, match="HTTP 502"):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_exec_end_event_without_exit_code_is_rejected() -> None:
    """结束事件缺 exitCode 时不能默认成功——那是假成功的形状。"""
    execution_channel = _build_isolated_channel(
        encode_connect_frame(json.dumps({"event": {"end": {"exited": True}}}).encode())
    )

    with pytest.raises(E2bProtocolError, match="缺少 exitCode"):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_exec_end_event_with_error_is_rejected() -> None:
    """结束事件自带错误时按协议异常处理,不能当作退出码 0 的成功。"""
    execution_channel = _build_isolated_channel(
        encode_connect_frame(
            json.dumps({"event": {"end": {"exitCode": 0, "error": "killed: oom"}}}).encode()
        )
    )

    with pytest.raises(E2bProtocolError, match="结束事件带错误"):
        execution_channel.run_command(
            "echo hi",
            timeout_seconds=30,
            cwd="/workspace",
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )


def test_endpoint_config_and_handle_repr_hide_credentials() -> None:
    """端点配置与句柄的 repr 不展开密钥,避免被随手打进日志。"""
    endpoint_config = E2bEndpointConfig(
        api_url="https://api.sandbox.example.test",
        api_key="secret-api-key-value",
        domain="",
        template_id="zata-sandbox",
        timeout_seconds=600,
        username="user",
        allow_internet_access=False,
    )
    sandbox_handle = E2bSandboxHandle(
        sandbox_id="sb-1",
        envd_base_url="https://49983-sb-1.example.test",
        access_token="secret-access-token-value",
        timeout_seconds=600,
    )

    assert "secret-api-key-value" not in repr(endpoint_config)
    assert "secret-access-token-value" not in repr(sandbox_handle)


# ---------------------------------------------------------------------------
# 执行通道解码语义
# ---------------------------------------------------------------------------


def test_exec_decodes_stdout_stderr_and_exit_code() -> None:
    """多帧 stdout/stderr 被合并,退出码取自结束事件。"""
    execution_channel = _build_isolated_channel(
        build_exec_response_body(
            stdout_chunks=[b"out-1\n", b"out-2\n"],
            stderr_chunks=[b"err-1\n", b""],
            exit_code=7,
        )
    )

    execution_outcome = execution_channel.run_command(
        "exit 7",
        timeout_seconds=30,
        cwd="/workspace",
        max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
    )

    assert execution_outcome.stdout_bytes == b"out-1\nout-2\n"
    assert execution_outcome.stderr_bytes == b"err-1\n"
    assert execution_outcome.exit_code == 7
    assert execution_outcome.truncated is False


def test_exec_marks_truncation_at_output_cap() -> None:
    """超过上限的输出被丢弃并标记截断。"""
    execution_channel = _build_isolated_channel(
        build_exec_response_body(
            stdout_chunks=[b"x" * (MAX_SANDBOX_OUTPUT_BYTES + 1000)],
            stderr_chunks=[b""],
            exit_code=0,
        )
    )

    execution_outcome = execution_channel.run_command(
        "big",
        timeout_seconds=30,
        cwd="/workspace",
        max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
    )

    assert execution_outcome.truncated is True
    assert len(execution_outcome.stdout_bytes) == MAX_SANDBOX_OUTPUT_BYTES


# ---------------------------------------------------------------------------
# Provider 与 Session
# ---------------------------------------------------------------------------


def test_provider_reports_unavailable_when_probe_fails() -> None:
    """控制面探测失败时后端不可用并给出原因,不抛异常中断启动。"""
    fake_service = FakeCloudSandboxService(probe_status_code=503)
    sandbox_provider = _build_provider(fake_service)

    assert sandbox_provider.is_available() is False
    assert "503" in (sandbox_provider.availability_detail() or "")


def test_acquire_creates_verifies_and_reuses_sandbox() -> None:
    """首次 acquire 建沙箱并校验工作区,后续 acquire 复用同一沙箱并续期。"""
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)

    first_session = sandbox_provider.acquire("thread-1")
    second_session = sandbox_provider.acquire("thread-1")

    assert first_session.session_key == second_session.session_key
    assert len(fake_service.sandboxes) == 1
    # 命令必须在沙箱内被 timeout 包裹:客户端超时只会放弃等待,命令仍在云上跑。
    assert fake_service.bounded_commands[0].startswith("timeout --kill-after=5s ")
    assert " /bin/sh -lc " in fake_service.bounded_commands[0]
    assert fake_service.renewed_timeouts == [_ENDPOINT_CONFIG.timeout_seconds]


def test_acquire_recreates_reclaimed_sandbox() -> None:
    """沙箱被回收后 acquire 重新创建,不把死沙箱继续交给执行器。"""
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)
    first_session = sandbox_provider.acquire("thread-1")

    fake_service.sandboxes.clear()
    fake_service.files.clear()
    recreated_session = sandbox_provider.acquire("thread-1")

    assert recreated_session.session_key != first_session.session_key


def test_acquire_destroys_sandbox_when_template_workspace_is_unusable() -> None:
    """执行模板不合格时明确失败,并销毁刚创建的沙箱避免留下孤儿。"""
    fake_service = FakeCloudSandboxService(workspace_writable=False)
    sandbox_provider = _build_provider(fake_service)

    with pytest.raises(RuntimeError, match="工作区初始化失败"):
        sandbox_provider.acquire("thread-1")

    assert fake_service.destroyed_sandbox_ids
    assert fake_service.sandboxes == {}


def test_acquire_maps_workspace_exec_rejection_to_template_diagnosis() -> None:
    """执行通道直接拒绝工作目录时,报错指向"模板不合格"而不是裸协议错误。

    实测形态:模板没有 ``/workspace`` 时,服务端在执行前就以 HTTP 400
    ``cwd '/workspace' does not exist`` 拒绝,命令根本没有机会以退出码作答。
    """
    fake_service = FakeCloudSandboxService(exec_rejection_status=400)
    sandbox_provider = _build_provider(fake_service)

    with pytest.raises(RuntimeError, match="工作区不可用") as raised_error:
        sandbox_provider.acquire("thread-1")

    assert "执行模板需预建" in str(raised_error.value)
    assert fake_service.destroyed_sandbox_ids
    assert fake_service.sandboxes == {}


def test_release_renews_and_destroy_removes_sandbox() -> None:
    """release 续期保活, destroy 真正销毁并使云侧列表清空。"""
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)
    acquired_session = sandbox_provider.acquire("thread-1")

    sandbox_provider.release("thread-1")
    assert fake_service.renewed_timeouts == [_ENDPOINT_CONFIG.timeout_seconds]
    assert sandbox_provider.active_sandbox_ids() == [acquired_session.session_key]

    sandbox_provider.destroy("thread-1")
    assert fake_service.destroyed_sandbox_ids == [acquired_session.session_key]
    assert sandbox_provider.active_sandbox_ids() == []


def test_release_drops_cache_when_sandbox_was_reclaimed() -> None:
    """沙箱已被回收时 release 丢弃本地映射,下次 acquire 重建。"""
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)
    first_session = sandbox_provider.acquire("thread-1")

    fake_service.sandboxes.clear()
    fake_service.files.clear()
    sandbox_provider.release("thread-1")

    rebuilt_session = sandbox_provider.acquire("thread-1")
    assert rebuilt_session.session_key != first_session.session_key


def test_shared_file_listing_rules_reject_truncated_and_tolerate_missing_directory() -> None:
    """三档共享的枚举规则:截断即拒绝,目录不存在才按空列表处理。"""
    from backend.core.shared.interfaces.sandbox_provider import SandboxExecutionResult
    from backend.infrastructure.sandbox.sandbox_rules import (
        build_file_listing_command,
        decode_file_listing,
    )

    assert build_file_listing_command("/workspace/outputs") == (
        "find /workspace/outputs -type f -print0"
    )
    assert decode_file_listing(
        SandboxExecutionResult(output="/workspace/outputs/a.csv\0", exit_code=0, truncated=False)
    ) == ["/workspace/outputs/a.csv"]
    assert (
        decode_file_listing(
            SandboxExecutionResult(output="find: no such dir", exit_code=1, truncated=False)
        )
        == []
    )
    with pytest.raises(RuntimeError, match="列表过长"):
        decode_file_listing(
            SandboxExecutionResult(output="/truncated", exit_code=0, truncated=True)
        )


def test_acquire_rebuilds_when_control_plane_forgot_the_sandbox() -> None:
    """控制面已无此沙箱(而 envd 仍在服务、身份标记完好)时也必须重建。

    这是控制面判据的负控:只有"控制面还在不在"这一问被真正问了,这条用例才会通过。
    实测形态是销毁后 ``GET /sandboxes/{id}`` 立刻 404,而执行通道仍以 200 返回另一个
    环境的结果。
    """
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)
    first_session = sandbox_provider.acquire("thread-1")

    fake_service.forget_sandbox_in_control_plane(first_session.session_key)

    rebuilt_session = sandbox_provider.acquire("thread-1")
    assert rebuilt_session.session_key != first_session.session_key


def test_control_plane_reports_sandbox_existence() -> None:
    """``sandbox_exists`` 按官方 getInfo 的 200/404 判定。"""
    from backend.infrastructure.sandbox.e2b_control_plane import E2bControlPlane

    fake_service = FakeCloudSandboxService()
    control_plane = E2bControlPlane(
        config=_ENDPOINT_CONFIG, http_client=fake_service.create_client()
    )
    created_handle = control_plane.create_sandbox()

    assert control_plane.sandbox_exists(created_handle.sandbox_id) is True
    fake_service.forget_sandbox_in_control_plane(created_handle.sandbox_id)
    assert control_plane.sandbox_exists(created_handle.sandbox_id) is False


def test_session_detects_swapped_sandbox_instead_of_reporting_empty_success() -> None:
    """沙箱被回收后网关返回另一个干净环境时,必须报"沙箱已不是本会话的",而不是成功。

    这是最危险的一条边界:实测销毁后执行通道仍以 HTTP 200 返回另一个环境的
    结果(退出码 0、文件系统为空)。若不加识别,产物导出会列出零个文件,最终以
    "无产物但成功"收尾。
    """
    fake_service = FakeCloudSandboxService()
    sandbox_provider = _build_provider(fake_service)
    swapped_session = sandbox_provider.acquire("thread-1")

    # 目标环境被换掉:身份标记随之消失。
    fake_service.replace_files_keeping_identity(swapped_session.sandbox_id, {})
    fake_service.files[swapped_session.sandbox_id] = {}

    assert swapped_session.is_alive() is False
    with pytest.raises(E2bSandboxNotFoundError, match="身份校验失败"):
        swapped_session.execute("echo hello", timeout_seconds=10)
    with pytest.raises(E2bSandboxNotFoundError):
        swapped_session.list_files("/workspace/outputs")

    rebuilt_session = sandbox_provider.acquire("thread-1")
    assert rebuilt_session.session_key != swapped_session.session_key


def test_session_uploads_files_and_rejects_escaping_paths() -> None:
    """文件写入落到云沙箱,越界路径在发出请求前就被拒绝。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")

    sandbox_session.upload_files(
        [SandboxFileWrite(sandbox_path="/workspace/inputs/r1/rates.csv", content=b"a,b\n")]
    )
    assert (
        fake_service.files_of(sandbox_session.sandbox_id)["/workspace/inputs/r1/rates.csv"]
        == b"a,b\n"
    )

    with pytest.raises(ValueError, match="绝对 POSIX 路径"):
        sandbox_session.upload_files(
            [SandboxFileWrite(sandbox_path="../../etc/passwd", content=b"x")]
        )


def test_session_downloads_files_per_item_error() -> None:
    """逐项成功/失败语义:缺失文件只标注该项失败。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")
    sandbox_session.upload_files(
        [SandboxFileWrite(sandbox_path="/workspace/outputs/report.csv", content=b"ok")]
    )

    file_reads = sandbox_session.download_files(
        ["/workspace/outputs/report.csv", "/workspace/outputs/missing.csv"]
    )

    assert file_reads[0].content == b"ok"
    assert file_reads[0].error is None
    assert file_reads[1].content is None
    assert file_reads[1].error is not None


def test_session_lists_outputs_and_refuses_truncated_listing() -> None:
    """目录文件被枚举;列表被截断时拒绝按不完整结果导出。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")
    sandbox_session.upload_files(
        [SandboxFileWrite(sandbox_path="/workspace/outputs/a.csv", content=b"a")]
    )
    assert sandbox_session.list_files("/workspace/outputs") == ["/workspace/outputs/a.csv"]

    fake_service.replace_files_keeping_identity(
        sandbox_session.sandbox_id,
        {f"/workspace/outputs/generated-{index:05d}-{'x' * 20}.csv": b"y" for index in range(4000)},
    )
    with pytest.raises(RuntimeError, match="列表过长"):
        sandbox_session.list_files("/workspace/outputs")


def test_session_truncates_oversized_command_output() -> None:
    """命令输出超过上限时标记截断。"""
    fake_service = FakeCloudSandboxService(
        command_responder=lambda _command: ("x" * (MAX_SANDBOX_OUTPUT_BYTES + 10), "", 0)
    )
    sandbox_session = _build_provider(fake_service).acquire("thread-1")

    execution_result = sandbox_session.execute("produce-much-output", timeout_seconds=30)

    assert execution_result.truncated is True
    assert len(execution_result.output) == MAX_SANDBOX_OUTPUT_BYTES


def test_replace_runtime_assets_swaps_root_atomically() -> None:
    """运行资产整体替换:旧内容消失、新内容到位、不留暂存目录。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")

    sandbox_session.replace_runtime_assets(
        [SandboxFileWrite(sandbox_path=_FIRST_STAGED_SKILL_ASSET_PATH, content=b"first")]
    )
    sandbox_session.replace_runtime_assets(
        [SandboxFileWrite(sandbox_path=_SKILL_ASSET_PATH, content=b"second")]
    )

    stored_files = fake_service.files_of(sandbox_session.sandbox_id)
    assert stored_files[_SKILL_ASSET_PATH] == b"second"
    assert _FIRST_STAGED_SKILL_ASSET_PATH not in stored_files
    assert not any(".staging" in stored_path for stored_path in stored_files)


def test_replace_runtime_assets_rejects_paths_outside_root() -> None:
    """运行资产路径必须位于资产根目录之下。"""
    fake_service = FakeCloudSandboxService()
    sandbox_session = _build_provider(fake_service).acquire("thread-1")

    with pytest.raises(ValueError, match="运行资产路径必须位于"):
        sandbox_session.replace_runtime_assets(
            [SandboxFileWrite(sandbox_path="/workspace/outputs/evil.py", content=b"x")]
        )


# ---------------------------------------------------------------------------
# 配置解析与装配失败闭合
# ---------------------------------------------------------------------------


def _write_e2b_config(config_file_path: Path, *, e2b_section: str) -> None:
    """写入一份以云沙箱为后端的配置。"""
    config_file_path.write_text(
        f"""
[sandbox_agent]
provider = "e2b"
command_timeout_seconds = 120
{e2b_section}
""",
        encoding="utf-8",
    )


def test_e2b_config_parses_endpoint_template_and_defaults(tmp_path: Path) -> None:
    """云沙箱配置段被解析,密钥只以环境变量别名出现。"""
    config_file_path = tmp_path / "config.toml"
    _write_e2b_config(
        config_file_path,
        e2b_section="""
[sandbox_agent.e2b]
api_url = "https://api.sandbox.example.test/"
template_id = "zata-sandbox"
""",
    )

    sandbox_config = load_sandbox_agent_config(config_file_path)

    assert sandbox_config is not None
    assert sandbox_config.e2b is not None
    assert sandbox_config.e2b.api_url == "https://api.sandbox.example.test"
    assert sandbox_config.e2b.api_key_env == "E2B_API_KEY"
    assert sandbox_config.e2b.allow_internet_access is False
    assert sandbox_config.egress.mode == "none"


def test_e2b_config_maps_internet_access_to_open_egress(tmp_path: Path) -> None:
    """显式放开出网时,出站策略同步为 open,而不是"看着关着其实开着"。"""
    config_file_path = tmp_path / "config.toml"
    _write_e2b_config(
        config_file_path,
        e2b_section="""
[sandbox_agent.e2b]
api_url = "https://api.sandbox.example.test"
template_id = "zata-sandbox"
allow_internet_access = true
""",
    )

    sandbox_config = load_sandbox_agent_config(config_file_path)

    assert sandbox_config is not None
    assert sandbox_config.egress.mode == "open"


@pytest.mark.parametrize(
    ("e2b_section", "expected_message"),
    [
        ("", "必须提供 \\[sandbox_agent.e2b\\] 段"),
        ('[sandbox_agent.e2b]\ntemplate_id = "zata-sandbox"', "缺少 api_url"),
        ('[sandbox_agent.e2b]\napi_url = "https://x.test"', "缺少 template_id"),
    ],
)
def test_e2b_config_rejects_incomplete_section(
    tmp_path: Path, e2b_section: str, expected_message: str
) -> None:
    """段缺失或关键项缺失时 fail-fast,不注册"根本没配上"的后端。"""
    config_file_path = tmp_path / "config.toml"
    _write_e2b_config(config_file_path, e2b_section=e2b_section)

    with pytest.raises(SandboxAgentConfigError, match=expected_message):
        load_sandbox_agent_config(config_file_path)


def test_unknown_provider_is_rejected(tmp_path: Path) -> None:
    """未知后端取值被拒绝,而不是静默回落到文件系统档。"""
    config_file_path = tmp_path / "config.toml"
    config_file_path.write_text(
        '[sandbox_agent]\nprovider = "aliyun-fc"\n',
        encoding="utf-8",
    )

    with pytest.raises(SandboxAgentConfigError, match="只支持"):
        load_sandbox_agent_config(config_file_path)


def _e2b_sandbox_config() -> SandboxAgentConfig:
    """构造一份云沙箱档配置对象,用于装配路径测试。"""
    from backend.infrastructure.config.sandbox_settings import E2bSandboxSettings

    return SandboxAgentConfig(
        provider="e2b",
        image="unused",
        command_timeout_seconds=120,
        workspace_root="unused",
        memory_limit="1g",
        model=None,
        egress=SandboxEgressPolicy(mode="none"),
        skills_paths=(),
        e2b=E2bSandboxSettings(
            api_url="https://api.sandbox.example.test",
            api_key_env="E2B_API_KEY",
            template_id="zata-sandbox",
            timeout_seconds=600,
            username="user",
            allow_internet_access=False,
        ),
    )


def test_missing_credential_does_not_register_sandbox_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """凭据缺失时装配失败闭合:返回 None,不产生任何宿主执行回落。"""
    from backend.composition import sandbox_wiring

    monkeypatch.delenv("E2B_API_KEY", raising=False)
    monkeypatch.setattr(
        sandbox_wiring, "load_sandbox_agent_config", lambda *_args, **_kwargs: _e2b_sandbox_config()
    )

    assembled_provider = sandbox_wiring.build_sandbox_provider()

    assert assembled_provider is None
