import os
import sys
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .llm_client import LLMClient
    from .context_loader import ContextLoader
    from .yaml_parser import extract_yaml_from_response, parse_frontmatter
except ImportError:
    # Fallback for when run as script
    from llm_client import LLMClient
    from context_loader import ContextLoader
    from yaml_parser import extract_yaml_from_response, parse_frontmatter

SYSTEM_PROMPT = """
You are the Head Librarian of a strict Obsidian Vault. 
Your goal is to organize raw notes into a structured system.

### INPUT DATA
1. **Raw Note Content**: The user's scratchpad.
2. **Context**: The System Instructions, Tag Glossary, and Project Codes.

### YOUR TASKS
1. **Analyze**: Understand the note's intent (Meeting, Idea, Task, Reference).
2. **Classify**: Assign the correct `type`, `status`, and `code` (if applicable).
3. **Enrich**: Add a descriptive `title` and relevant `tags` (from the Glossary only).
4. **File**: Suggest the correct folder path based on the Areas/Projects structure.

### OUTPUT FORMAT
Return the valid YAML Frontmatter ONLY, wrapped in ```yaml blocks.
Do not change the body of the note yet.

Example Output:
```yaml
title: "PEPS-P4 - PRD Draft"
folder: "20. Projects/Pepsi Scaling Phase"
type: "product-idea"
status: "draft"
tags: [ "type/product-idea", "client/pepsi" ]
code: "PEPS-P4"
```
"""


class NoteProcessor:
    def __init__(self, vault_root: str):
        """
        Initialize the note processor.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.llm = LLMClient(system_instruction=SYSTEM_PROMPT)
        self.loader = ContextLoader(vault_root)
    
    def process_note(self, note_content: str) -> dict:
        """
        Sends the note + context to Gemini and gets the Metadata suggestions.
        
        Args:
            note_content: The raw note content to analyze
            
        Returns:
            dict: Parsed frontmatter metadata as dictionary
            
        Raises:
            Exception: If LLM call fails or YAML parsing fails
        """
        # 1. Get Context
        context = self.loader.get_full_context()
        
        # 2. Build the User Prompt
        user_prompt = f"""
=== CONTEXT ===
{context}

=== RAW NOTE ===
{note_content}

Please generate the Metadata Frontmatter for this note.
"""

        # 3. Call LLM
        response = self.llm.generate_content(user_prompt)
        
        # 4. Extract and parse YAML from response
        yaml_content = extract_yaml_from_response(response)
        if not yaml_content:
            raise ValueError("No YAML content found in LLM response")
        
        frontmatter = parse_frontmatter(yaml_content)
        
        return frontmatter
