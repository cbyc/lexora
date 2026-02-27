"""Unit tests for GeminiEmbeddingModel — all API calls are mocked."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge.embedder import GeminiEmbeddingModel


class TestGeminiEmbeddingModel:
    def test_raises_value_error_when_api_key_is_none(self):
        """Missing API key must raise ValueError at construction, not at call time."""
        with pytest.raises(ValueError, match="google_api_key"):
            GeminiEmbeddingModel(model_name="models/text-embedding-004", api_key=None)

    def test_encode_returns_list_of_float(self):
        """encode() must return a list of floats."""
        embedding_value = MagicMock()
        embedding_value.values = [0.1, 0.2, 0.3]
        mock_result = MagicMock()
        mock_result.embeddings = [embedding_value]

        with patch("google.genai.Client") as MockClient:
            MockClient.return_value.models.embed_content.return_value = mock_result
            model = GeminiEmbeddingModel(
                model_name="models/text-embedding-004", api_key="fake-key"
            )
            result = asyncio.run(model.encode("hello world"))

        assert result == [0.1, 0.2, 0.3]

    def test_encode_forwards_model_name_to_api(self):
        """encode() must pass the configured model name to the API."""
        model_name = "models/text-embedding-004"
        embedding_value = MagicMock()
        embedding_value.values = [0.1]
        mock_result = MagicMock()
        mock_result.embeddings = [embedding_value]

        with patch("google.genai.Client") as MockClient:
            mock_embed = MockClient.return_value.models.embed_content
            mock_embed.return_value = mock_result
            model = GeminiEmbeddingModel(model_name=model_name, api_key="fake-key")
            asyncio.run(model.encode("hello"))

        mock_embed.assert_called_once_with(
            model=model_name,
            contents="hello",
        )

    def test_encode_forwards_text_as_contents(self):
        """encode() must pass the input text as 'contents' to the API."""
        embedding_value = MagicMock()
        embedding_value.values = [0.1]
        mock_result = MagicMock()
        mock_result.embeddings = [embedding_value]

        with patch("google.genai.Client") as MockClient:
            mock_embed = MockClient.return_value.models.embed_content
            mock_embed.return_value = mock_result
            model = GeminiEmbeddingModel(
                model_name="models/text-embedding-004", api_key="fake-key"
            )
            asyncio.run(model.encode("my test text"))

        call_kwargs = mock_embed.call_args.kwargs
        assert call_kwargs["contents"] == "my test text"
