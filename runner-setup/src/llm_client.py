import os
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

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


class LLMClient:
    def __init__(self, model_name="gemini-2.5-flash", system_instruction=None):
        """
        Initialise the Gemini Client.
        Expects GEMINI_API_KEY to be set in environment variables.
        
        Args:
            model_name: Name of the Gemini model to use (default: "gemini-2.5-flash")
            system_instruction: Optional system instruction to pass to the model (default: None)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("❌ Error: GEMINI_API_KEY environment variable not set.")

        genai.configure(api_key=api_key)
        
        # Pass system instruction to model if provided
        if system_instruction:
            self.model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
            print(f"🤖 LLM Client initialized with model: {model_name} (with system instruction)")
        else:
            self.model = genai.GenerativeModel(model_name)
            print(f"🤖 LLM Client initialized with model: {model_name}")

    def generate_content(self, prompt: str) -> str:
        """
        Sends a prompt to the model and returns the text response.
        
        Args:
            prompt: The text prompt to send to the model
            
        Returns:
            str: The model's text response
            
        Raises:
            Exception: If the API call fails
        """
        try:
            # Configure for deterministic output (temperature=0)
            # This is crucial for automation/formatting tasks
            config = GenerationConfig(
                temperature=0.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )

            response = self.model.generate_content(
                prompt,
                generation_config=config
            )
            
            return response.text

        except Exception as e:
            print(f"🔥 API Error: {str(e)}")
            raise e

    def generate_proposal(self, instructions: str, body: str, context: str, skeleton: str, model_name="gemini-2.5-flash") -> str:
        """
        Generates a multi-file proposal using the Architect system prompt.
        
        Args:
            instructions: User instructions from the note
            body: Raw note content
            context: Full vault context (system instructions, glossary, code registry)
            skeleton: Vault skeleton map for deep linking
            model_name: Name of the Gemini model to use
            
        Returns:
            str: Raw LLM response with %%FILE: markers
        """
        # Create architect model with architect system prompt
        architect_model = genai.GenerativeModel(model_name, system_instruction=ARCHITECT_SYSTEM_PROMPT)
        
        # Build user prompt
        user_prompt = f"""
=== USER INSTRUCTIONS ===
{instructions}

=== RAW NOTE CONTENT ===
{body}

=== VAULT CONTEXT ===
{context}

Please generate a multi-file proposal following the output format.
"""
        
        try:
            # Configure for deterministic output
            config = GenerationConfig(
                temperature=0.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
            
            response = architect_model.generate_content(
                user_prompt,
                generation_config=config
            )
            
            return response.text
            
        except Exception as e:
            print(f"🔥 API Error in generate_proposal: {str(e)}")
            raise e
