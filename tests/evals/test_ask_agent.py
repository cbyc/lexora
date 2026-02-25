"""Pydantic Evals dataset for the AskAgent.

These cases are written BEFORE the system prompt is finalised — they serve as a
written specification of required behaviour. Run them with a real API key:

    LLM_MODEL=google-gla:gemini-2.0-flash GEMINI_API_KEY=... uv run pytest tests/evals/

They are kept separate from the unit tests because they require a live LLM call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from src.ask_agent import PydanticAIAskAgent
from src.models import NOT_FOUND, AskResponse, Chunk

# ---------------------------------------------------------------------------
# Inputs type
# ---------------------------------------------------------------------------


@dataclass
class AskAgentInputs:
    question: str
    chunks: list[Chunk]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class SourcesSubsetOfChunks(Evaluator[AskAgentInputs, AskResponse, None]):
    """Mechanical check: every returned source must exist in the provided chunks."""

    def evaluate(
        self, ctx: EvaluatorContext[AskAgentInputs, AskResponse, None]
    ) -> float:
        chunk_sources = {c.source for c in ctx.inputs.chunks}
        fabricated = [s for s in ctx.output.sources if s not in chunk_sources]
        return 0.0 if fabricated else 1.0


@dataclass
class NotFoundHasNoSources(Evaluator[AskAgentInputs, AskResponse, None]):
    """Mechanical check: NOT_FOUND response must have empty sources."""

    def evaluate(
        self, ctx: EvaluatorContext[AskAgentInputs, AskResponse, None]
    ) -> float:
        if ctx.output.text == NOT_FOUND:
            return 0.0 if ctx.output.sources else 1.0
        return 1.0  # not applicable


@dataclass
class IsGrounded(Evaluator[AskAgentInputs, AskResponse, None]):
    """LLM-as-judge: the answer must not go beyond the provided context."""

    def evaluate(
        self, ctx: EvaluatorContext[AskAgentInputs, AskResponse, None]
    ) -> float:
        if ctx.output.text == NOT_FOUND:
            return 1.0  # vacuously grounded

        model = os.environ.get("LLM_MODEL", "google-gla:gemini-2.0-flash")
        judge: Agent[None, bool] = Agent(
            model,
            result_type=bool,
            system_prompt=(
                "You are a grounding judge. Given a context and an answer, "
                "return true if the answer is fully supported by the context "
                "and does not introduce information not present in the context. "
                "Return false otherwise."
            ),
        )
        context_text = "\n\n".join(
            f"SOURCE: {c.source}\n{c.text}" for c in ctx.inputs.chunks
        )
        prompt = f"Context:\n{context_text}\n\nAnswer:\n{ctx.output.text}"
        result = judge.run_sync(prompt)
        return 1.0 if result.output else 0.0


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

_GIL_CHUNK = Chunk(
    text=(
        "The Global Interpreter Lock (GIL) is a mutex in CPython that prevents "
        "multiple native threads from executing Python bytecodes simultaneously. "
        "It simplifies memory management but limits multi-core CPU utilisation."
    ),
    source="notes/python_concurrency.txt",
    chunk_index=0,
)

_ASYNC_CHUNK = Chunk(
    text=(
        "Python's asyncio library provides cooperative multitasking via an event loop. "
        "Unlike threads, coroutines yield control explicitly using await, making race "
        "conditions less likely without needing a GIL."
    ),
    source="https://docs.python.org/3/library/asyncio.html",
    chunk_index=0,
)

dataset: Dataset[AskAgentInputs, AskResponse, None] = Dataset(
    cases=[
        Case(
            name="answerable",
            inputs=AskAgentInputs(
                question="What is Python's GIL?",
                chunks=[_GIL_CHUNK],
            ),
            # Expected: non-empty answer; sources must contain the chunk source.
        ),
        Case(
            name="unanswerable",
            inputs=AskAgentInputs(
                question="What is the capital of France?",
                chunks=[_GIL_CHUNK],
            ),
            expected_output=AskResponse(text=NOT_FOUND, sources=[]),
        ),
        Case(
            name="empty_context",
            inputs=AskAgentInputs(
                question="What is Python's GIL?",
                chunks=[],
            ),
            expected_output=AskResponse(text=NOT_FOUND, sources=[]),
        ),
        Case(
            name="multi_source",
            inputs=AskAgentInputs(
                question="Compare the GIL and asyncio as concurrency strategies.",
                chunks=[_GIL_CHUNK, _ASYNC_CHUNK],
            ),
            # Expected: answer references both sources.
        ),
        Case(
            name="sources_not_fabricated",
            inputs=AskAgentInputs(
                question="What is Python's GIL?",
                chunks=[_GIL_CHUNK],
            ),
            # SourcesSubsetOfChunks evaluator covers this mechanically.
        ),
    ],
    evaluators=[
        SourcesSubsetOfChunks(),
        NotFoundHasNoSources(),
        IsGrounded(),
    ],
)


# ---------------------------------------------------------------------------
# Task function — the function evaluated on each case
# ---------------------------------------------------------------------------


async def run_ask_agent(inputs: AskAgentInputs) -> AskResponse:
    model = os.environ.get("LLM_MODEL", "google-gla:gemini-2.0-flash")
    agent = PydanticAIAskAgent(model)
    return await agent.answer(inputs.question, inputs.chunks)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.evals
def test_ask_agent_evals():
    """Run the eval dataset against the real LLM. Requires a provider API key."""
    report = dataset.evaluate_sync(run_ask_agent)
    report.print(include_input=True, include_output=True)

    averages = report.averages()
    assert averages is not None
    assert averages.scores["SourcesSubsetOfChunks"] == 1.0
    assert averages.scores["NotFoundHasNoSources"] == 1.0
    assert averages.scores["IsGrounded"] >= 0.8
