from __future__ import annotations

from functools import cache

from google.generativeai.types import HarmBlockThreshold, HarmCategory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq


@cache
def default_llm() -> ChatGoogleGenerativeAI:
    # chat = ChatGroq(model_name="mixtral-8x7b-32768")
    # return chat


    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        },
        convert_system_message_to_human=True,
    )


@cache
def aux_llm() -> ChatGoogleGenerativeAI:
    return default_llm()
