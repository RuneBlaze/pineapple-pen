from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_THINKING_LEVEL = "minimal"


SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


@dataclass
class GeminiLLM:
    model: str = GEMINI_MODEL
    thinking_level: str = GEMINI_THINKING_LEVEL
    _client: genai.Client | None = field(default=None, init=False, repr=False)

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            load_dotenv()
            self._client = genai.Client()
        return self._client

    def generate_content(
        self,
        contents: str,
        *,
        response_schema: Any | None = None,
        response_json_schema: dict[str, Any] | None = None,
    ) -> types.GenerateContentResponse:
        config = types.GenerateContentConfig(
            safety_settings=SAFETY_SETTINGS,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level),
        )
        if response_schema is not None or response_json_schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema
            config.response_json_schema = response_json_schema
        return self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

    def invoke(self, input: str) -> str:
        response = self.generate_content(input)
        return response.text or ""


@cache
def default_llm() -> GeminiLLM:
    return GeminiLLM()


@cache
def aux_llm() -> GeminiLLM:
    return default_llm()
