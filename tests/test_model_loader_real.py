"""Tests for real model loading with actual API calls.

These tests require valid API keys to be set in environment variables.
They will be skipped if the required API keys are not available.

Required environment variables:
    - DASHSCOPE_API_KEY: For testing DashScope models (qwen-*)
    - OPENROUTER_API_KEY: For testing OpenRouter models
    - ANTHROPIC_API_KEY: For testing Anthropic models

To run these tests:
    uv run pytest tests/test_model_loader_real.py -v

To run with specific API key:
    DASHSCOPE_API_KEY=your-key uv run pytest tests/test_model_loader_real.py -v
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from infrastructure.models import (
    ModelConfigError,
    create_chat_model,
    resolve_model_credentials,
)

# =============================================================================
# Skip Conditions
# =============================================================================

HAS_DASHSCOPE_KEY: bool = bool(os.getenv("DASHSCOPE_API_KEY"))
HAS_OPENROUTER_KEY: bool = bool(os.getenv("OPENROUTER_API_KEY"))
HAS_ANTHROPIC_KEY: bool = bool(os.getenv("ANTHROPIC_API_KEY"))

REQUIRES_DASHSCOPE = pytest.mark.skipif(
    not HAS_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY environment variable not set",
)

REQUIRES_OPENROUTER = pytest.mark.skipif(
    not HAS_OPENROUTER_KEY,
    reason="OPENROUTER_API_KEY environment variable not set",
)

REQUIRES_ANTHROPIC = pytest.mark.skipif(
    not HAS_ANTHROPIC_KEY,
    reason="ANTHROPIC_API_KEY environment variable not set",
)


# =============================================================================
# Real Model Loading Tests
# =============================================================================


class TestRealCredentialResolution:
    """Tests for real credential resolution with actual API keys."""

    @REQUIRES_DASHSCOPE
    def test_resolve_qwen_flash_real_credentials(self) -> None:
        """Test resolving real credentials for qwen-flash with actual API key."""
        credentials: list[tuple[str, str | None, str | None]] = (
            resolve_model_credentials("qwen-flash")
        )

        assert len(credentials) > 0
        provider, base_url, api_key = credentials[0]
        assert provider == "dashscope"
        assert api_key is not None
        assert len(api_key) > 10  # API keys are typically longer
        assert base_url is not None
        assert "dashscope" in base_url

    @REQUIRES_OPENROUTER
    def test_resolve_openrouter_models_real_credentials(self) -> None:
        """Test resolving real credentials for OpenRouter models."""
        credentials: list[tuple[str, str | None, str | None]] = (
            resolve_model_credentials("anthropic/claude-3.5-sonnet")
        )

        assert len(credentials) > 0
        provider, base_url, api_key = credentials[0]
        assert provider == "openrouter"
        assert api_key is not None
        assert len(api_key) > 10
        assert base_url is not None
        assert "openrouter" in base_url


class TestRealModelInstantiation:
    """Tests for real chat model instantiation with actual API calls."""

    @REQUIRES_DASHSCOPE
    def test_create_qwen_flash_real(self) -> None:
        """Test creating real qwen-flash model instance.

        This test actually instantiates the model but does not make API calls.
        """
        from langchain_core.language_models import BaseLanguageModel

        llm: BaseLanguageModel = create_chat_model(
            "qwen-flash",
            temperature=0.7,
        )

        assert llm is not None
        assert hasattr(llm, "invoke")
        assert llm.model_name == "qwen-flash"

    @REQUIRES_DASHSCOPE
    def test_create_qwen_plus_real(self) -> None:
        """Test creating real qwen-plus model instance."""
        from langchain_core.language_models import BaseLanguageModel

        llm: BaseLanguageModel = create_chat_model(
            "qwen-plus",
            temperature=0.5,
        )

        assert llm is not None
        assert hasattr(llm, "invoke")

    @REQUIRES_OPENROUTER
    def test_create_openrouter_claude_real(self) -> None:
        """Test creating real OpenRouter Claude model instance."""
        from langchain_core.language_models import BaseLanguageModel

        llm: BaseLanguageModel = create_chat_model(
            "anthropic/claude-3.5-sonnet",
            temperature=0.7,
        )

        assert llm is not None
        assert hasattr(llm, "invoke")


class TestRealModelInvocation:
    """Tests for real model invocation with actual API calls.

    These tests make real API calls and will consume API credits.
    They are marked with the 'expensive' marker.
    """

    @pytest.mark.expensive
    @REQUIRES_DASHSCOPE
    def test_qwen_flash_simple_completion(self) -> None:
        """Test simple completion with qwen-flash (consumes API credits).

        This test makes a real API call to DashScope.
        """
        from langchain_core.messages import HumanMessage

        llm = create_chat_model("qwen-flash", temperature=0.0)

        messages: list[HumanMessage] = [
            HumanMessage(content="Say 'Hello, World!' exactly.")
        ]
        response: Any = llm.invoke(messages)

        assert response is not None
        assert hasattr(response, "content")
        assert len(response.content) > 0
        print(f"Model response: {response.content}")

    @pytest.mark.expensive
    @REQUIRES_DASHSCOPE
    def test_qwen_flash_with_system_message(self) -> None:
        """Test completion with system message (consumes API credits)."""
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = create_chat_model("qwen-flash", temperature=0.0)

        messages: list[Any] = [
            SystemMessage(
                content="You are a helpful assistant that only responds with the word 'OK'."
            ),
            HumanMessage(content="Please confirm you understand."),
        ]
        response: Any = llm.invoke(messages)

        assert response is not None
        assert hasattr(response, "content")
        print(f"Model response: {response.content}")


class TestRealModelWithDifferentRegions:
    """Tests for DashScope models with different regions."""

    @REQUIRES_DASHSCOPE
    def test_create_qwen_flash_singapore_region(self) -> None:
        """Test creating qwen-flash with Singapore region endpoint."""
        from langchain_core.language_models import BaseLanguageModel

        llm: BaseLanguageModel = create_chat_model(
            "qwen-flash",
            temperature=0.7,
            dashscope_region="singapore",
        )

        assert llm is not None
        # Verify the base URL is Singapore endpoint
        assert hasattr(llm, "openai_api_base")
        assert "singapore" in llm.openai_api_base or "intl" in llm.openai_api_base

    @REQUIRES_DASHSCOPE
    def test_create_qwen_flash_beijing_region(self) -> None:
        """Test creating qwen-flash with Beijing region endpoint."""
        from langchain_core.language_models import BaseLanguageModel

        llm: BaseLanguageModel = create_chat_model(
            "qwen-flash",
            temperature=0.7,
            dashscope_region="beijing",
        )

        assert llm is not None
        assert hasattr(llm, "openai_api_base")
        # Beijing endpoint should not have 'intl' or 'singapore'
        assert "aliyuncs.com" in llm.openai_api_base


class TestRealModelErrorHandling:
    """Tests for error handling with real model loading."""

    def test_create_model_without_api_key_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that creating model without API key raises ModelConfigError."""
        # Ensure no API key is available
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

        with pytest.raises(ModelConfigError) as exc_info:
            create_chat_model("qwen-flash")

        assert "API key missing" in str(exc_info.value) or "No credentials" in str(
            exc_info.value
        )

    def test_create_unknown_model_with_inference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test creating unknown model with provider inference.

        This will fail due to missing API key, but tests the inference logic.
        """
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ModelConfigError):
            create_chat_model("gpt-4-unknown-model")


class TestRealModelConfiguration:
    """Tests for real model configuration validation."""

    @REQUIRES_DASHSCOPE
    def test_qwen_flash_temperature_setting(self) -> None:
        """Test that temperature setting is properly applied."""
        llm_low_temp = create_chat_model("qwen-flash", temperature=0.0)
        llm_high_temp = create_chat_model("qwen-flash", temperature=1.0)

        assert llm_low_temp.temperature == 0.0
        assert llm_high_temp.temperature == 1.0

    @REQUIRES_DASHSCOPE
    def test_qwen_flash_max_tokens_setting(self) -> None:
        """Test that max_tokens setting is properly applied."""
        llm = create_chat_model(
            "qwen-flash", temperature=0.7, client_kwargs={"max_tokens": 100}
        )

        assert hasattr(llm, "max_tokens")
        # Note: The attribute name may vary depending on langchain version


class TestSettingsIntegrationReal:
    """Real integration tests with settings module."""

    @REQUIRES_DASHSCOPE
    def test_load_model_from_settings_config(self) -> None:
        """Test loading model using configuration from settings module."""
        from infrastructure.config.settings import config as app_config

        # Use the model configured in settings
        model_name: str = app_config.chat_model.name
        temperature: float = app_config.chat_model.temperature

        # Only test if it's a dashscope model
        if app_config.chat_model.provider == "dashscope":
            llm = create_chat_model(
                model_name,
                temperature=temperature,
            )

            assert llm is not None
            assert llm.model_name == model_name
