import os
import google.generativeai as genai
from google.generativeai.types import GenerationConfig


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
