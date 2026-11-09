"""验证 Nacos 文档格式兼容与 dotenv 的字面值及拒绝策略。"""

import pytest

from backend.infrastructure.config.providers.nacos_helpers import parse_nacos_config_document
from backend.infrastructure.config.providers.protocol import ConfigProviderError


def test_dotenv_preserves_literals_and_runtime_snapshot() -> None:
    """密码不展开引用；空值、引号、多行和嵌套运行时快照保持语义。"""
    snapshot = parse_nacos_config_document(
        '# application settings\nAPP_NAME=demo\nPASSWORD="${UNCHANGED}#pass"\n'
        "EMPTY=\nCERT='first\nsecond'\nruntime_config='{\"enabled\":true}'\n"
    )
    assert snapshot == {
        "APP_NAME": "demo",
        "PASSWORD": "${UNCHANGED}#pass",
        "EMPTY": "",
        "CERT": "first\nsecond",
        "runtime_config": {"enabled": True},
    }


@pytest.mark.parametrize(
    "invalid_document",
    [
        "",
        "# comment only",
        "PASSWORD=secret\nPASSWORD=other",
        "PASSWORD",
        "lowercase=secret",
        'PASSWORD="unterminated',
        "PASSWORD=secret\x00",
        '{"PASSWORD":"secret",}',
        "[]",
        "null",
        'runtime_config="[]"',
    ],
)
def test_invalid_document_is_rejected_without_echo(invalid_document: str) -> None:
    """无效正文不能静默覆盖或作为异常消息输出。"""
    with pytest.raises(ConfigProviderError) as failure:
        parse_nacos_config_document(invalid_document)
    assert "secret" not in str(failure.value)


def test_existing_json_document_remains_typed() -> None:
    """兼容原 JSON 数字、布尔及运行时配置契约。"""
    assert parse_nacos_config_document(
        '{"DB_PORT":5432,"ENABLED":true,"runtime_config":{"flag":false}}'
    ) == {"DB_PORT": 5432, "ENABLED": True, "runtime_config": {"flag": False}}
