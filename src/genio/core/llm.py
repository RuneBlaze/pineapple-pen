from __future__ import annotations

from functools import cache

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq


@cache
def default_llm() -> ChatGoogleGenerativeAI:
    return ChatGroq(
        model="mixtral-8x7b-32768",
        temperature=0.2,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )


@cache
def aux_llm() -> ChatGoogleGenerativeAI:
    return default_llm()
