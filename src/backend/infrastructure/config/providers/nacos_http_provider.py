"""通过 Nacos 3 HTTP Client API 读取并轮询 JSON 或 dotenv 配置。"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Mapping

import httpx

from backend.infrastructure.config.settings import ConfigProviderSettings

from .nacos_helpers import parse_nacos_config_document
from .protocol import ConfigProviderError, RuntimeConfigListener, RuntimeConfigSnapshot

_LOGGER: logging.Logger = logging.getLogger(__name__)
_LOGIN_PATH: str = "/nacos/v3/auth/user/login"
_CONFIG_PATH: str = "/nacos/v3/client/cs/config"


class NacosHttpConfigProvider:
    """使用 HTTP API 读取配置，适合只能经 HTTP/HTTPS 出站的部署。"""

    def __init__(self, settings: ConfigProviderSettings) -> None:
        """初始化 Nacos HTTP provider。

        Args:
            settings: Nacos HTTPS 地址、配置范围、轮询间隔和账号设置。
        """
        self._settings = settings
        self._http_client = httpx.AsyncClient(
            base_url=settings.nacos_server_addr.strip().rstrip("/"),
            timeout=httpx.Timeout(10.0),
            follow_redirects=False,
            trust_env=False,
        )
        self._access_token: str = ""
        self._access_token_expires_at: float = 0.0
        self._last_config_md5: str | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._listener: RuntimeConfigListener | None = None

    async def load(self) -> RuntimeConfigSnapshot:
        """读取指定 Data ID 的当前 JSON 或 dotenv 配置。

        Returns:
            已解析的运行时配置快照。

        Raises:
            ConfigProviderError: 登录、读取或配置解析失败。
        """
        config_content, config_md5 = await self._fetch_config()
        config_snapshot: RuntimeConfigSnapshot = parse_nacos_config_document(config_content)
        self._last_config_md5 = config_md5
        return config_snapshot

    async def subscribe(self, listener: RuntimeConfigListener) -> None:
        """启动定时轮询；配置变更时向 listener 发布完整快照。

        Args:
            listener: 接收 Nacos 新配置快照的异步回调。
        """
        self._listener = listener
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_config())

    async def close(self) -> None:
        """停止轮询并关闭 HTTP 客户端。"""
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        await self._http_client.aclose()

    async def _poll_config(self) -> None:
        while True:
            await asyncio.sleep(self._settings.nacos_poll_interval_seconds)
            try:
                config_content, config_md5 = await self._fetch_config()
                if config_md5 == self._last_config_md5:
                    continue
                try:
                    config_snapshot: RuntimeConfigSnapshot = parse_nacos_config_document(
                        config_content
                    )
                except ConfigProviderError as parse_error:
                    self._last_config_md5 = config_md5
                    _LOGGER.warning(
                        "忽略无效的 Nacos HTTP 配置更新 data_id=%s group=%s: %s",
                        self._settings.nacos_data_id,
                        self._settings.nacos_group,
                        parse_error,
                    )
                    continue
                if self._listener is not None:
                    await self._listener(config_snapshot)
                self._last_config_md5 = config_md5
            except Exception as poll_error:  # noqa: BLE001
                _LOGGER.warning("轮询 Nacos HTTP 配置失败：%s", poll_error)

    async def _fetch_config(self) -> tuple[str, str]:
        access_token: str = await self._get_access_token()
        request_params: dict[str, str] = {
            "dataId": self._settings.nacos_data_id,
            "groupName": self._settings.nacos_group,
        }
        if self._settings.nacos_namespace_id.strip():
            request_params["namespaceId"] = self._settings.nacos_namespace_id.strip()

        for auth_attempt in range(2):
            try:
                config_response: httpx.Response = await self._http_client.get(
                    _CONFIG_PATH,
                    params=request_params,
                    headers={"accessToken": access_token},
                )
            except httpx.HTTPError as request_error:
                raise ConfigProviderError("请求 Nacos HTTP 配置接口失败。") from request_error
            if config_response.status_code in (401, 403) and auth_attempt == 0:
                self._access_token = ""
                access_token = await self._get_access_token()
                continue
            try:
                config_response.raise_for_status()
                config_payload: object = config_response.json()
            except (httpx.HTTPError, ValueError) as response_error:
                raise ConfigProviderError("Nacos HTTP 配置接口返回错误。") from response_error
            return self._parse_config_response(config_payload)
        raise ConfigProviderError("Nacos HTTP 配置接口认证失败。")

    async def _get_access_token(self) -> str:
        if self._access_token and self._access_token_expires_at - time.monotonic() > 30:
            return self._access_token

        try:
            login_response: httpx.Response = await self._http_client.post(
                _LOGIN_PATH,
                data={
                    "username": self._settings.nacos_username,
                    "password": self._settings.nacos_password.get_secret_value(),
                },
            )
            login_response.raise_for_status()
            login_payload: object = login_response.json()
        except (httpx.HTTPError, ValueError) as login_error:
            raise ConfigProviderError("登录 Nacos HTTP API 失败。") from login_error
        if not isinstance(login_payload, Mapping):
            raise ConfigProviderError("Nacos HTTP 登录响应格式无效。")
        access_token_value: object = login_payload.get("accessToken")
        token_ttl_value: object = login_payload.get("tokenTtl")
        if not isinstance(access_token_value, str) or not access_token_value:
            raise ConfigProviderError("Nacos HTTP 登录响应缺少 accessToken。")
        if not isinstance(token_ttl_value, (int, float)) or token_ttl_value <= 0:
            raise ConfigProviderError("Nacos HTTP 登录响应缺少有效 tokenTtl。")
        self._access_token = access_token_value
        self._access_token_expires_at = time.monotonic() + max(
            1.0,
            float(token_ttl_value) * 0.9,
        )
        return self._access_token

    @staticmethod
    def _parse_config_response(config_payload: object) -> tuple[str, str]:
        if not isinstance(config_payload, Mapping):
            raise ConfigProviderError("Nacos HTTP 配置响应格式无效。")
        if config_payload.get("code") != 0:
            raise ConfigProviderError("Nacos HTTP 配置读取未成功。")
        config_result: object = config_payload.get("data")
        if not isinstance(config_result, Mapping):
            raise ConfigProviderError("Nacos HTTP 配置响应缺少 data 字段。")
        result_code: object = config_result.get("resultCode")
        if result_code not in (None, 200):
            raise ConfigProviderError("Nacos HTTP 配置读取未成功。")
        config_content: object = config_result.get("content")
        if not isinstance(config_content, str):
            raise ConfigProviderError("Nacos HTTP 配置响应缺少 content 字段。")
        config_md5_value: object = config_result.get("md5")
        config_md5: str = (
            config_md5_value
            if isinstance(config_md5_value, str) and config_md5_value
            else hashlib.sha256(config_content.encode("utf-8")).hexdigest()
        )
        return config_content, config_md5
