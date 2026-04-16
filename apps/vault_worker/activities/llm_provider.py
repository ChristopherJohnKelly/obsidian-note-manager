"""LLM provider abstractions for vault-worker Activities.

Defines the abstract base that Activities depend on, plus the real GeminiProvider.
FakeLLMProvider (in tests/mocks/fake_llm.py) implements the same interface.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMProviderBase(ABC):
    """Abstract base for all LLM providers.

    Activities call generate_proposal/generate_fix on whatever provider
    is injected via llm.configure_provider(). Tests inject FakeLLMProvider;
    production injects GeminiProvider.
    """

    @abstractmethod
    def generate_proposal(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        """Generate a filing proposal. Returns raw response with %%FILE%%...%%END%% markers."""

    @abstractmethod
    def generate_fix(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        """Generate a fix proposal. Returns raw response with %%FILE%%...%%END%% markers."""


ARCHITECT_SYSTEM_PROMPT = """You are an Obsidian vault filing assistant.

INPUT:
1. User Instructions (intent)
2. Raw Note Content
3. Vault Context (code registry, related notes)
4. Vault Skeleton (valid link targets)

OUTPUT FORMAT — use these exact delimiters:

%%FILE%%
path: <vault-relative-path>.md
---
<frontmatter YAML>
---
<note body with [[Deep Links]] to skeleton entries>
%%END%%

RULES:
1. Always use %%FILE%%...%%END%% delimiters.
2. Use vault-relative paths only (e.g. "20. Projects/Alpha/Note.md").
3. Frontmatter must be valid YAML.
4. Only link to notes that exist in the Vault Skeleton.
"""


class GeminiProvider(LLMProviderBase):  # pragma: no cover
    """Real Gemini LLM provider using google-generativeai.

    Configured via GEMINI_API_KEY environment variable.
    No unit tests — validated in manual E2E test only.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        import google.generativeai as genai  # lazy import — not available in test env

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=key)
        self._model_name = model_name

    def generate_proposal(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig

        model = genai.GenerativeModel(
            self._model_name,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
        )
        user_prompt = (
            f"=== USER INSTRUCTIONS ===\n{instructions}\n\n"
            f"=== RAW NOTE CONTENT ===\n{body}\n\n"
            f"=== VAULT CONTEXT ===\n{context}\n\n"
            f"=== VAULT SKELETON ===\n{skeleton}"
        )
        config = GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )
        response = model.generate_content(user_prompt, generation_config=config)
        return response.text

    def generate_fix(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig

        model = genai.GenerativeModel(
            self._model_name,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
        )
        user_prompt = (
            f"=== FIX INSTRUCTIONS ===\n{instructions}\n\n"
            f"=== CURRENT NOTE CONTENT ===\n{body}\n\n"
            f"=== VAULT CONTEXT ===\n{context}\n\n"
            f"=== VAULT SKELETON ===\n{skeleton}"
        )
        config = GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )
        response = model.generate_content(user_prompt, generation_config=config)
        return response.text
