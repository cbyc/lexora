import asyncio

from google import genai


class GeminiEmbeddingModel:
    def __init__(self, model_name: str, api_key: str | None):
        if api_key is None:
            raise ValueError("google_api_key is required for GeminiEmbeddingModel")
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    async def encode(self, text: str) -> list[float]:
        result = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self._model_name,
            contents=text,
        )
        return result.embeddings[0].values
