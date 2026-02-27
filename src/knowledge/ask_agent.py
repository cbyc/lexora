from pydantic_ai import Agent

from models import AskResponse, Chunk, NOT_FOUND

SYSTEM_PROMPT = f"""You are a retrieval-augmented assistant. Answer the user's question \
using ONLY the provided context. Do not use any external knowledge.

Rules:
- If the context contains a relevant answer, respond with your answer in `text` and \
list ONLY the source URLs or paths you drew from in `sources`. Each entry in `sources` \
must be the exact string that appears after "SOURCE:" in the context block — never a \
reference number like [1] or [2].
- If the context does not contain a relevant answer, set `text` to exactly \
"{NOT_FOUND}" and `sources` to an empty list.
- Never include a source in `sources` that you did not draw from in your answer.
"""


class PydanticAIAskAgent:
    def __init__(self, model: str):
        self._agent: Agent[None, AskResponse] = Agent(
            model,
            output_type=AskResponse,
            system_prompt=SYSTEM_PROMPT,
        )

    def _format_context(self, chunks: list[Chunk]) -> str:
        if not chunks:
            return ""
        parts = []
        for chunk in chunks:
            parts.append(f"SOURCE: {chunk.source}\n{chunk.text}")
        return "\n\n".join(parts)

    async def answer(self, question: str, chunks: list[Chunk]) -> AskResponse:
        context = self._format_context(chunks)
        prompt = (
            f"Context:\n{context}\n\nQuestion: {question}"
            if context
            else f"Context: (none)\n\nQuestion: {question}"
        )
        result = await self._agent.run(prompt)
        return result.output
