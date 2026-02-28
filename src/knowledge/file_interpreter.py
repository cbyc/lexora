"""GeminiFileInterpreter — interprets file bytes via the Gemini multimodal API."""

import asyncio
import mimetypes

from google import genai
from google.genai import types


class GeminiFileInterpreter:
    def __init__(self, model: str, api_key: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def interpret(
        self, file_bytes: bytes, filename: str, system_prompt: str
    ) -> str:
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            mime_type = "application/octet-stream"

        file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        contents = [file_part, system_prompt]

        result = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=contents,
        )
        return result.text
