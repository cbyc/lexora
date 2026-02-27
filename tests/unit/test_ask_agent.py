"""Unit tests for PydanticAIAskAgent — all LLM calls are mocked."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.knowledge.ask_agent import PydanticAIAskAgent
from src.models import NOT_FOUND, AskResponse, Chunk


def make_chunks(*pairs: tuple[str, str]) -> list[Chunk]:
    """Build a list of Chunk objects from (text, source) pairs."""
    return [Chunk(text=t, source=s, chunk_index=i) for i, (t, s) in enumerate(pairs)]


class TestContextFormatting:
    def test_single_chunk_formatted_correctly(self):
        """A single chunk should use the SOURCE: prefix with the exact source path."""
        agent = PydanticAIAskAgent.__new__(PydanticAIAskAgent)
        chunks = make_chunks(("GIL text", "notes/gil.txt"))
        result = agent._format_context(chunks)
        assert "SOURCE: notes/gil.txt" in result
        assert "GIL text" in result

    def test_multiple_chunks_each_have_source_prefix(self):
        """Each chunk should have its own SOURCE: prefix with the correct path."""
        agent = PydanticAIAskAgent.__new__(PydanticAIAskAgent)
        chunks = make_chunks(("text a", "a.txt"), ("text b", "b.txt"))
        result = agent._format_context(chunks)
        assert "SOURCE: a.txt" in result
        assert "SOURCE: b.txt" in result

    def test_no_reference_numbers_in_context(self):
        """Context must not contain [N] reference numbers that the LLM might cite."""
        agent = PydanticAIAskAgent.__new__(PydanticAIAskAgent)
        chunks = make_chunks(("text a", "a.txt"), ("text b", "b.txt"))
        result = agent._format_context(chunks)
        assert "[1]" not in result
        assert "[2]" not in result

    def test_empty_chunks_returns_empty_string(self):
        """No chunks should produce an empty context string."""
        agent = PydanticAIAskAgent.__new__(PydanticAIAskAgent)
        assert agent._format_context([]) == ""


class TestAnswer:
    def _make_agent_with_mock(self, mock_output):
        """Helper: create PydanticAIAskAgent with a mocked pydantic-ai Agent."""
        with patch("src.knowledge.ask_agent.Agent") as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=MagicMock(output=mock_output))
            agent = PydanticAIAskAgent("google-gla:gemini-2.0-flash")
            agent._agent = instance
        return agent

    def test_returns_ask_response_from_llm(self):
        """answer() should return the AskResponse produced by the LLM."""
        expected = AskResponse(text="GIL is a mutex.", sources=["notes/gil.txt"])
        agent = self._make_agent_with_mock(expected)
        chunks = make_chunks(("GIL text", "notes/gil.txt"))
        result = asyncio.run(agent.answer("What is the GIL?", chunks))
        assert result == expected

    def test_passes_question_and_context_to_run(self):
        """The formatted context and question must be forwarded to agent.run."""
        expected = AskResponse(text="The GIL is a lock.", sources=["notes/gil.txt"])
        with patch("src.knowledge.ask_agent.Agent") as MockAgent:
            instance = MockAgent.return_value
            instance.run = AsyncMock(return_value=MagicMock(output=expected))
            agent = PydanticAIAskAgent("openai:gpt-4o")
            agent._agent = instance

        chunks = make_chunks(("GIL text", "notes/gil.txt"))
        asyncio.run(agent.answer("What is the GIL?", chunks))

        call_args = instance.run.call_args
        prompt_sent = call_args[0][0]
        assert "What is the GIL?" in prompt_sent
        assert "notes/gil.txt" in prompt_sent

    def test_not_found_response_returned_as_is(self):
        """If the LLM returns a NOT_FOUND response it is passed through unchanged."""
        not_found = AskResponse(text=NOT_FOUND, sources=[])
        agent = self._make_agent_with_mock(not_found)
        result = asyncio.run(agent.answer("irrelevant question", []))
        assert result.text == NOT_FOUND
        assert result.sources == []
