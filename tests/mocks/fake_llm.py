"""Deterministic LLM stub for testing. No API calls — returns hardcoded responses."""

from packages.shared.models import ChatMessage


class FakeLLMProvider:
    """Deterministic LLM that returns hardcoded responses. No API calls.

    Same input always produces the same output. Any method not explicitly
    implemented raises NotImplementedError so test failures are visible.
    """

    FAKE_PROPOSAL = """%%FILE%%
path: 30. Areas/1. Test Area/AREA - Filed Note.md
---
type: content
status: active
title: "Filed Note"
aliases: ["Test Filed"]
tags: ["type/content"]
---
# Filed Note
Fake content for testing.
%%END%%"""

    FAKE_FIX = """%%FILE%%
path: {original_path}
---
type: content
status: active
title: "Fixed Note"
aliases: ["Fixed"]
tags: ["type/content"]
---
# Fixed Note
Fixed content.
%%END%%"""

    def generate_proposal(self, instructions: str, body: str,
                          context: str, skeleton: str) -> str:
        """Return a hardcoded filing proposal with %%FILE%% markers."""
        return self.FAKE_PROPOSAL

    def generate_fix(self, instructions: str, body: str,
                     context: str, skeleton: str) -> str:
        """Return a hardcoded fix proposal with %%FILE%% markers."""
        return self.FAKE_FIX

    def generate_chat_response(self, messages: list[ChatMessage]) -> str:
        return "Here is your answer."

    def generate_react_response(self, mode: str) -> str:
        if mode == "tool_call":
            return "TOOL: get_skeleton\nARGS: {}"
        return "Here is a direct response."

    def __getattr__(self, name: str):
        raise NotImplementedError(
            f"FakeLLMProvider.{name}() is not implemented. "
            "Add it explicitly if needed for testing."
        )
