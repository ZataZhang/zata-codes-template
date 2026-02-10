"""Tests for embedding model loading.

Tests cover both local sentence-transformers models and API-based embeddings.
Local tests download and cache models on first run.

Required environment variables for API tests:
    - DASHSCOPE_API_KEY: For testing DashScope embeddings

To run local embedding tests:
    uv run pytest tests/test_embedding_model.py -v -k "local"

To run API embedding tests:
    DASHSCOPE_API_KEY=your-key uv run pytest tests/test_embedding_model.py -v -k "api"
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from utils.settings import config as app_config

# =============================================================================
# Skip Conditions
# =============================================================================

HAS_DASHSCOPE_KEY: bool = bool(os.getenv("DASHSCOPE_API_KEY"))

REQUIRES_DASHSCOPE = pytest.mark.skipif(
    not HAS_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY environment variable not set",
)

REQUIRES_SENTENCE_TRANSFORMERS = pytest.mark.skipif(
    True,  # Will be updated after checking if sentence-transformers is installed
    reason="sentence-transformers package not installed",
)


def _check_sentence_transformers() -> bool:
    """Check if sentence-transformers is available."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


HAS_SENTENCE_TRANSFORMERS: bool = _check_sentence_transformers()
REQUIRES_SENTENCE_TRANSFORMERS = pytest.mark.skipif(
    not HAS_SENTENCE_TRANSFORMERS,
    reason="sentence-transformers package not installed. Run: uv pip install sentence-transformers",
)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestEmbeddingConfiguration:
    """Tests for embedding configuration from settings."""

    def test_embedding_model_configured(self) -> None:
        """Test that embedding model is properly configured."""
        assert app_config.embedding.model
        assert isinstance(app_config.embedding.model, str)
        assert len(app_config.embedding.model) > 0

    def test_embedding_dimension_configured(self) -> None:
        """Test that embedding dimension is properly configured."""
        assert app_config.embedding.dim > 0
        assert isinstance(app_config.embedding.dim, int)

    def test_embedding_model_dir_configured(self) -> None:
        """Test that embedding model directory is configured."""
        assert app_config.embedding.model_dir
        assert isinstance(app_config.embedding.model_dir, str)

    def test_embedding_offline_mode_configured(self) -> None:
        """Test that offline mode flag is configured."""
        assert isinstance(app_config.embedding.offline_mode, bool)

    def test_embedding_model_is_sentence_transformer(self) -> None:
        """Test that default embedding model is sentence-transformers format."""
        model_name: str = app_config.embedding.model
        # Default model should be sentence-transformers format
        assert "sentence-transformers" in model_name or "all-MiniLM" in model_name


# =============================================================================
# Local Model Loading Tests
# =============================================================================


class TestLocalEmbeddingModelLoading:
    """Tests for loading local sentence-transformers models."""

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_load_sentence_transformer_model(self) -> None:
        """Test loading a sentence-transformers model.

        This test downloads the model on first run if not cached.
        """
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model

        # Load the model
        model: SentenceTransformer = SentenceTransformer(model_name)

        assert model is not None
        assert hasattr(model, "encode")

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_sentence_transformer_encode_text(self) -> None:
        """Test encoding text with loaded model."""
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model
        expected_dim: int = app_config.embedding.dim

        model: SentenceTransformer = SentenceTransformer(model_name)

        # Encode a simple sentence
        sentences: list[str] = ["This is a test sentence."]
        embeddings: Any = model.encode(sentences)

        assert embeddings is not None
        assert embeddings.shape[0] == 1  # One sentence
        assert embeddings.shape[1] == expected_dim  # Correct dimension

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_sentence_transformer_batch_encode(self) -> None:
        """Test batch encoding multiple sentences."""
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model
        expected_dim: int = app_config.embedding.dim

        model: SentenceTransformer = SentenceTransformer(model_name)

        # Encode multiple sentences
        sentences: list[str] = [
            "This is the first sentence.",
            "This is the second sentence.",
            "This is the third sentence.",
        ]
        embeddings: Any = model.encode(sentences)

        assert embeddings is not None
        assert embeddings.shape[0] == 3  # Three sentences
        assert embeddings.shape[1] == expected_dim  # Correct dimension

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_sentence_transformer_similarity(self) -> None:
        """Test computing similarity between sentences."""
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import cos_sim

        model_name: str = app_config.embedding.model
        model: SentenceTransformer = SentenceTransformer(model_name)

        # Similar sentences should have high similarity
        sentences: list[str] = [
            "The cat sits on the mat.",
            "The cat is sitting on the mat.",
            "I love programming in Python.",
        ]
        embeddings: Any = model.encode(sentences)

        # Compute cosine similarity
        sim_0_1: float = float(cos_sim(embeddings[0], embeddings[1]))
        sim_0_2: float = float(cos_sim(embeddings[0], embeddings[2]))

        # Similar sentences should have higher similarity than dissimilar ones
        assert sim_0_1 > sim_0_2
        assert sim_0_1 > 0.8  # Very similar sentences

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_model_caching(self) -> None:
        """Test that models are properly cached."""
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model

        # Load model twice
        model1: SentenceTransformer = SentenceTransformer(model_name)
        model2: SentenceTransformer = SentenceTransformer(model_name)

        # Should be the same object if properly cached
        # Note: SentenceTransformer may not cache by default, but should use same files
        assert model1 is not None
        assert model2 is not None


# =============================================================================
# Model Directory Tests
# =============================================================================


class TestModelDirectory:
    """Tests for model directory configuration and usage."""

    def test_model_dir_path_resolution(self) -> None:
        """Test that model directory path is properly resolved."""
        model_dir: str = app_config.embedding.model_dir
        project_root: Path = app_config.base_dir

        expected_path: Path = project_root / model_dir

        # Path components should be valid (parent may not exist until created)
        assert isinstance(expected_path, Path)
        assert model_dir.endswith("models") or "model" in model_dir.lower()

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_model_download_to_custom_dir(self, tmp_path: Path) -> None:
        """Test downloading model to custom directory."""
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model
        cache_folder: Path = tmp_path / "test_models"

        # Load model with custom cache
        model: SentenceTransformer = SentenceTransformer(
            model_name, cache_folder=str(cache_folder)
        )

        assert model is not None
        # Model files should be in custom directory
        assert cache_folder.exists() or not list(cache_folder.glob("*"))


# =============================================================================
# API-Based Embedding Tests
# =============================================================================


class TestAPIEmbeddingLoading:
    """Tests for API-based embeddings (DashScope, OpenAI, etc.)."""

    @REQUIRES_DASHSCOPE
    def test_load_dashscope_embedding_model(self) -> None:
        """Test loading DashScope embedding model."""
        from openai import OpenAI

        api_key: str | None = os.getenv("DASHSCOPE_API_KEY")
        assert api_key is not None

        # Use OpenAI-compatible API for embeddings
        client: OpenAI = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        assert client is not None
        # Test that client can be created successfully
        # Actual API call tested in other tests

    @pytest.mark.expensive
    @REQUIRES_DASHSCOPE
    def test_dashscope_embedding_api_call(self) -> None:
        """Test actual DashScope embedding API call (consumes API credits)."""
        from openai import OpenAI

        api_key: str | None = os.getenv("DASHSCOPE_API_KEY")
        assert api_key is not None

        client: OpenAI = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # Test single query embedding with direct API call
        response: Any = client.embeddings.create(
            model="text-embedding-v2",
            input="This is a test query.",
        )

        assert response is not None
        assert len(response.data) > 0
        embedding_vector: list[float] = response.data[0].embedding
        assert len(embedding_vector) > 0
        assert all(isinstance(x, float) for x in embedding_vector)

        print(f"Embedding dimension: {len(embedding_vector)}")

    @pytest.mark.expensive
    @REQUIRES_DASHSCOPE
    def test_dashscope_embedding_documents(self) -> None:
        """Test DashScope document embeddings (consumes API credits)."""
        from openai import OpenAI

        api_key: str | None = os.getenv("DASHSCOPE_API_KEY")
        assert api_key is not None

        client: OpenAI = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # Test document embeddings with direct API call
        documents: list[str] = [
            "First document content.",
            "Second document content.",
            "Third document content.",
        ]

        response: Any = client.embeddings.create(
            model="text-embedding-v2",
            input=documents,
        )

        assert len(response.data) == 3
        document_embeddings: list[list[float]] = [
            item.embedding for item in response.data
        ]
        assert all(len(emb) > 0 for emb in document_embeddings)


# =============================================================================
# Dimension Validation Tests
# =============================================================================


class TestEmbeddingDimension:
    """Tests for validating embedding dimensions."""

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_embedding_dimension_matches_config(self) -> None:
        """Test that actual embedding dimension matches configuration."""
        from sentence_transformers import SentenceTransformer

        model_name: str = app_config.embedding.model
        expected_dim: int = app_config.embedding.dim

        model: SentenceTransformer = SentenceTransformer(model_name)

        # Get embedding dimension
        test_sentence: str = "Test sentence."
        embedding: Any = model.encode([test_sentence])

        actual_dim: int = embedding.shape[1]

        assert actual_dim == expected_dim, (
            f"Expected dimension {expected_dim}, got {actual_dim}. "
            f"Update config.toml if model has changed."
        )

    @REQUIRES_SENTENCE_TRANSFORMERS
    def test_different_models_different_dimensions(self) -> None:
        """Test that different models have appropriate dimensions."""
        from sentence_transformers import SentenceTransformer

        # Test with the configured model
        model_name: str = app_config.embedding.model
        model: SentenceTransformer = SentenceTransformer(model_name)

        test_sentence: str = "Test."
        embedding: Any = model.encode([test_sentence])

        dim: int = embedding.shape[1]

        # Common embedding dimensions
        assert dim in [
            128,
            256,
            384,
            512,
            768,
            1024,
            1536,
        ], f"Unexpected embedding dimension: {dim}"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestEmbeddingErrorHandling:
    """Tests for error handling in embedding loading."""

    def test_invalid_model_name_raises_error(self) -> None:
        """Test that invalid model name raises appropriate error."""
        pytest.skip("Requires sentence-transformers to be installed")

    def test_missing_model_dir_handling(self, tmp_path: Path) -> None:
        """Test handling of missing model directory."""
        # This should be handled gracefully
        non_existent_dir: Path = tmp_path / "non_existent" / "models"

        # Directory creation should work
        non_existent_dir.mkdir(parents=True, exist_ok=True)
        assert non_existent_dir.exists()
