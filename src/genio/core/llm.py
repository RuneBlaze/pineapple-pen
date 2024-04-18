from __future__ import annotations

from functools import cache

from google.generativeai.types import HarmBlockThreshold, HarmCategory
from langchain_community.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI


@cache
def default_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-1.0-pro",
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        },
        convert_system_message_to_human=True,
    )


@cache
def aux_llm() -> ChatOllama:
    return default_llm()


# @cache
# def default_llm() -> ChatOpenAI:
#     return ChatOpenAI(model="gpt-3.5-turbo-0125")
# class LangFuseCallbackHandler(CallbackHandler):
#     """
#     A monkey-patched version of the LangFuseCallbackHandler that
#     works for LangChain Google Generative AI.
#     """
#
#     def on_llm_end(
#         self,
#         response: LLMResult,
#         *,
#         run_id: UUID,
#         parent_run_id: Optional[UUID] = None,
#         **kwargs: Any,
#     ) -> Any:
#         try:
#             self.log.debug(
#                 f"on llm end: run_id: {{run_id}} parent_run_id: {{parent_run_id}} response: {{response}} kwargs: {{kwargs}}"
#             )
#             if run_id not in self.runs:
#                 raise Exception("Run not found, see docs what to do in this case.")
#             else:
#                 generation = response.generations[-1][-1]
#                 extracted_response = (
#                     self._convert_message_to_dict(generation.message)
#                     if isinstance(generation, ChatGeneration)
#                     else _extract_raw_esponse(generation)
#                 )
#                 llm_usage = (
#                     None
#                     if response.llm_output is None
#                     else response.llm_output.get("token_usage")
#                 )
#
#                 self.runs[run_id] = self.runs[run_id].end(
#                     output=extracted_response, usage=llm_usage, version=self.version
#                 )
#
#                 self._update_trace(run_id, parent_run_id, extracted_response)
#
#         except Exception as e:
#             self.log.exception(e)
