from llm_client import LLMClient
import os


def main():
    print("--- Starting Gemini Connection Test ---")
    
    try:
        # 1. Initialize
        client = LLMClient()
        
        # 2. Define a simple prompt
        prompt = "Explain in one sentence why Obsidian is a good note-taking app."
        
        # 3. Call API
        print(f"\n📤 Sending prompt: '{prompt}'...")
        response = client.generate_content(prompt)
        
        # 4. Output
        print(f"\n✅ Response received:\n{response}")
        print("\n--- Test Passed ---")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
