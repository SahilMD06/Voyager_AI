"""A scripted tool-calling chat model for offline agent tests.

It replays a fixed list of AIMessages (including tool calls) so the real
LangChain agent loop, real tools and real validation can be exercised
without network access or an API key.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedToolModel(BaseChatModel):
    """Returns the next scripted message on every call."""

    script: list[AIMessage]
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedToolModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop=None,
                  run_manager=None, **kwargs: Any) -> ChatResult:
        message = self.script[min(self.cursor, len(self.script) - 1)]
        self.cursor += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def call(name: str, args: dict, call_id: str) -> dict:
    """Helper to build a tool-call dict."""
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}
