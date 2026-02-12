"""LLM adapters for AI operations."""

import os

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from src_v2.core.interfaces.ports import LLMProvider

ARCHITECT_SYSTEM_PROMPT = """
You are an Obsidian Assistant. Your goal is to organize notes and create structured knowledge.

INPUT:
1. User Instructions (Intent)
2. Raw Note Content
3. Vault Skeleton (Existing paths for deep linking)

OUTPUT FORMAT:
You must output a single text blob using these delimiters:

%%EXPLANATION%%
(Short reasoning: why you chose these folders/files)

%%FILE: <suggested_folder>/<suggested_filename>.md%%
---
title: <Title>
tags: [<tag1>, <tag2>]
folder: <folder_path>
---
<Content with [[Deep Links]] to Skeleton>

%%FILE: <another_folder>/<another_file>.md%%
...

RULES:
1. Always use the %%FILE: path%% delimiter.
2. Ensure frontmatter is valid YAML.
3. Do NOT invent links. Only link to items in the Vault Skeleton.
4. If the user asks to split a note, create multiple %%FILE%% blocks.
5. Extract folder paths from the suggested file paths.
"""


class GeminiAdapter(LLMProvider):
    """Adapter for Google Gemini API."""

    def __init__(
        self,
        *,
        model_name: str = "gemini-2.5-flash",
        api_key: str | None = None,
    ) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=key)
        self.model_name = model_name

    def _get_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )

    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(
            prompt,
            generation_config=self._get_generation_config(),
        )
        return response.text

    def generate_proposal(
        self,
        instructions: str,
        body: str,
        context: str,
        skeleton: str,
    ) -> str:
        """Generate a multi-file proposal. Returns raw LLM response with %%FILE%% markers."""
        architect_model = genai.GenerativeModel(
            self.model_name,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
        )
        user_prompt = f"""
=== USER INSTRUCTIONS ===
{instructions}

=== RAW NOTE CONTENT ===
{body}

=== VAULT CONTEXT ===
{context}

Please generate a multi-file proposal following the output format.
"""
        response = architect_model.generate_content(
            user_prompt,
            generation_config=self._get_generation_config(),
        )
        return response.text
