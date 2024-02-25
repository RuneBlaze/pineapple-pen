from __future__ import annotations

from functools import cache

from google.generativeai.types import HarmCategory, HarmBlockThreshold
from langchain_google_genai import ChatGoogleGenerativeAI


@cache
def default_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-pro",
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        },
    )


# @cache
# def default_llm() -> ChatOllama:
#     return ChatOllama(
#         model="openhermes:7b-mistral-v2-q5_0", base_url="http://192.168.40.9:11434"
#     )

# @cache
# def default_llm() -> ChatOpenAI:
#     return ChatOpenAI(model="gpt-3.5-turbo-0125")
