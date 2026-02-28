"""Tests for GeminiFileInterpreter."""

import asyncio
from unittest.mock import MagicMock, patch

from knowledge.file_interpreter import GeminiFileInterpreter


class TestGeminiFileInterpreter:
    def test_init_creates_genai_client(self):
        """Constructor should create a genai.Client with the given api_key."""
        with patch("knowledge.file_interpreter.genai.Client") as mock_cls:
            GeminiFileInterpreter(model="gemini-2.0-flash", api_key="test-key")
        mock_cls.assert_called_once_with(api_key="test-key")

    def test_interpret_returns_text(self):
        """interpret() should return the text from the LLM response."""
        mock_response = MagicMock()
        mock_response.text = "Extracted text from PDF."

        with patch("knowledge.file_interpreter.genai.Client") as mock_cls:
            mock_cls.return_value.models.generate_content.return_value = mock_response
            interpreter = GeminiFileInterpreter(model="gemini-2.0-flash", api_key="key")
            result = asyncio.run(
                interpreter.interpret(
                    file_bytes=b"%PDF-1.4 content",
                    filename="test.pdf",
                    system_prompt="Extract content.",
                )
            )

        assert result == "Extracted text from PDF."

    def test_interpret_calls_generate_content_with_model(self):
        """interpret() should call generate_content with the configured model."""
        mock_response = MagicMock()
        mock_response.text = "some text"

        with patch("knowledge.file_interpreter.genai.Client") as mock_cls:
            mock_generate = mock_cls.return_value.models.generate_content
            mock_generate.return_value = mock_response
            interpreter = GeminiFileInterpreter(model="gemini-2.0-flash", api_key="key")
            asyncio.run(
                interpreter.interpret(
                    file_bytes=b"data",
                    filename="doc.pdf",
                    system_prompt="Extract all text.",
                )
            )

        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs["model"] == "gemini-2.0-flash"

    def test_interpret_sends_two_content_parts(self):
        """interpret() should pass file bytes part and system prompt as two contents."""
        mock_response = MagicMock()
        mock_response.text = "ok"

        with patch("knowledge.file_interpreter.genai.Client") as mock_cls:
            mock_generate = mock_cls.return_value.models.generate_content
            mock_generate.return_value = mock_response
            interpreter = GeminiFileInterpreter(model="gemini-2.0-flash", api_key="key")
            asyncio.run(
                interpreter.interpret(
                    file_bytes=b"pdf bytes here",
                    filename="a.pdf",
                    system_prompt="prompt",
                )
            )

        contents = mock_generate.call_args.kwargs["contents"]
        assert len(contents) == 2
        # Second element is the plain system prompt string
        assert contents[1] == "prompt"
