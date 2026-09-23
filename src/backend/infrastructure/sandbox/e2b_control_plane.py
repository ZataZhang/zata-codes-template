"""云沙箱控制面客户端:创建、续期、销毁、列举与可达性探测。

控制面只做"沙箱这个环境存不存在、还能活多久",不承载命令与文件——那是执行通道的
事。二者分开的好处是:执行通道出问题不会掩盖控制面故障,而"沙箱已被回收"这类
终止性错误在控制面会被映射为 :class:`E2bSandboxNotFoundError`。

经实测确认的契约(2026-09-21):

* ``POST /sandboxes`` 返回 201,响应含裸 ``sandboxID``、``envdAccessToken`` 与
  ``domain``;``allow_internet_access: false`` 生效。
* ``POST /sandboxes/{id}/timeout`` 返回 204,用于续期。
* ``DELETE /sandboxes/{id}`` 返回 204。
* ``/pause`` 在本服务上未启用,因此"保留文件系统"只能靠续期而不是暂停。
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from backend.infrastructure.sandbox.e2b_protocol import (
    E2bEndpointConfig,
    E2bProtocolError,
    E2bSandboxHandle,
    build_envd_base_url,
    build_status_error,
    build_transport_error,
    decode_json_array,
    decode_json_object,
)

_API_KEY_HEADER = "X-API-KEY"
_CONTROL_PLANE_TIMEOUT_SECONDS = 30.0


class E2bControlPlane:
    """云沙箱控制面 HTTP 客户端。"""

    def __init__(
        self,
        *,
        config: E2bEndpointConfig,
        http_client: httpx.Client | None = None,
    ) -> None:
        """绑定端点配置与可复用的 HTTP 客户端。

        Args:
            config (E2bEndpointConfig): 云沙箱端点配置。
            http_client (httpx.Client | None): 复用的 HTTP 客户端;``None`` 时自建。
        """
        self._config = config
        self._http_client = http_client or httpx.Client(timeout=_CONTROL_PLANE_TIMEOUT_SECONDS)

    def probe(self) -> None:
        """探测控制面可达且凭据有效。

        Raises:
            E2bProtocolError: 端点不可达、凭据无效或返回非成功状态。
        """
        self._send(
            operation="探测",
            request_sender=lambda: self._http_client.get(
                f"{self._config.api_url}/templates", headers=self._auth_headers()
            ),
        )

    def create_sandbox(self) -> E2bSandboxHandle:
        """创建一个云沙箱。

        Returns:
            E2bSandboxHandle: 新建沙箱的访问句柄。

        Raises:
            E2bProtocolError: 创建失败,或响应缺少必要字段。
        """
        response = self._send(
            operation="创建沙箱",
            request_sender=lambda: self._http_client.post(
                f"{self._config.api_url}/sandboxes",
                headers=self._auth_headers(),
                json={
                    "templateID": self._config.template_id,
                    "timeout": self._config.timeout_seconds,
                    "allow_internet_access": self._config.allow_internet_access,
                },
            ),
        )
        created_payload = decode_json_object(response_text=response.text, action="创建沙箱")
        sandbox_id = str(created_payload.get("sandboxID") or "")
        access_token = str(created_payload.get("envdAccessToken") or "")
        response_domain = str(created_payload.get("domain") or "") or self._config.domain
        if not sandbox_id or not access_token or not response_domain:
            raise E2bProtocolError("云沙箱创建响应缺少 sandboxID / envdAccessToken / domain 字段")
        return E2bSandboxHandle(
            sandbox_id=sandbox_id,
            envd_base_url=build_envd_base_url(sandbox_id=sandbox_id, domain=response_domain),
            access_token=access_token,
            timeout_seconds=self._config.timeout_seconds,
        )

    def renew_sandbox(self, sandbox_id: str, *, timeout_seconds: int) -> None:
        """延长沙箱存活窗口。

        Args:
            sandbox_id (str): 裸沙箱标识。
            timeout_seconds (int): 新的存活窗口秒数。

        Raises:
            E2bProtocolError: 续期失败;沙箱已不存在时抛
                :class:`E2bSandboxNotFoundError`。
        """
        self._send(
            operation="续期沙箱",
            request_sender=lambda: self._http_client.post(
                f"{self._config.api_url}/sandboxes/{sandbox_id}/timeout",
                headers=self._auth_headers(),
                json={"timeout": timeout_seconds},
            ),
        )

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """销毁沙箱及其文件系统。

        沙箱不存在时按成功处理:销毁是幂等清理动作,重复调用不应该让调用方失败。

        Args:
            sandbox_id (str): 裸沙箱标识。

        Raises:
            E2bProtocolError: 除"不存在"以外的销毁失败。
        """
        self._send(
            operation="销毁沙箱",
            request_sender=lambda: self._http_client.delete(
                f"{self._config.api_url}/sandboxes/{sandbox_id}",
                headers=self._auth_headers(),
            ),
            tolerate_not_found=True,
        )

    def sandbox_exists(self, sandbox_id: str) -> bool:
        """查询沙箱是否仍存在于控制面(官方 ``Sandbox.getInfo``)。

        实测(2026-09-21):``GET /sandboxes/{id}`` 存活时返回 200,销毁后**立刻**返回 404
        ——而同一时刻执行通道仍会以 200 返回另一个环境的结果。因此这是判断"这个沙箱还在
        不在"最权威、也最便宜的判据;它和执行通道的身份自校验回答的是两个不同问题。

        Args:
            sandbox_id (str): 裸沙箱标识。

        Returns:
            bool: 控制面仍记得该沙箱为真。

        Raises:
            E2bProtocolError: 传输失败或返回非 404 的非成功状态。
        """
        response = self._send(
            operation="查询沙箱",
            request_sender=lambda: self._http_client.get(
                f"{self._config.api_url}/sandboxes/{sandbox_id}", headers=self._auth_headers()
            ),
            tolerate_not_found=True,
        )
        return response.status_code != 404

    def list_sandbox_ids(self) -> list[str]:
        """列出当前账号下仍存在的沙箱标识,供运维观测孤儿沙箱。

        实测(2026-09-21):该接口返回**裸数组**,且存在约 2 秒的最终一致延迟——刚创建
        的沙箱不会立刻出现在列表里,刚销毁的也不会立刻消失。因此它适合做"有没有长期
        遗留"的巡检,不适合做"这一步是否已经生效"的即时断言。

        Returns:
            list[str]: 沙箱标识列表。

        Raises:
            E2bProtocolError: 列举失败或响应不是数组。
        """
        response = self._send(
            operation="列举沙箱",
            request_sender=lambda: self._http_client.get(
                f"{self._config.api_url}/sandboxes", headers=self._auth_headers()
            ),
        )
        listed_sandbox_ids: list[str] = []
        for raw_sandbox in decode_json_array(response_text=response.text, action="列举沙箱"):
            sandbox_id = (
                str(raw_sandbox.get("sandboxID") or "")
                if isinstance(raw_sandbox, dict)
                else str(raw_sandbox)
            )
            if sandbox_id:
                listed_sandbox_ids.append(sandbox_id)
        return listed_sandbox_ids

    def _auth_headers(self) -> dict[str, str]:
        """返回控制面鉴权头。

        密钥只进请求头,不进异常消息与日志。
        """
        return {_API_KEY_HEADER: self._config.api_key}

    def _send(
        self,
        *,
        operation: str,
        request_sender: "Callable[[], httpx.Response]",
        tolerate_not_found: bool = False,
    ) -> httpx.Response:
        """发送一次控制面请求并把传输与状态错误映射为协议异常。

        Args:
            operation (str): 操作名,用于错误消息。
            request_sender (Callable[[], httpx.Response]): 实际发起请求的闭包。
            tolerate_not_found (bool): 目标不存在时是否按成功处理。

        Returns:
            httpx.Response: 成功响应。

        Raises:
            E2bProtocolError: 传输失败、目标不存在(未放行时)或状态码非成功。
        """
        try:
            response = request_sender()
        except httpx.HTTPError as transport_error:
            raise build_transport_error(action=operation, transport_error=transport_error) from (
                transport_error
            )
        if response.status_code < 400:
            return response
        if tolerate_not_found and response.status_code == 404:
            return response
        raise build_status_error(
            action=operation,
            status_code=response.status_code,
            response_body=response.text,
        )


__all__ = ["E2bControlPlane"]
