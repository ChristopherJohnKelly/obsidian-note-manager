import os
import sys
import re
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .llm_client import LLMClient
    from .context_loader import ContextLoader
    from .yaml_parser import extract_yaml_from_response, parse_frontmatter
    from .response_parser import ResponseParser
except ImportError:
    # Fallback for when run as script
    from llm_client import LLMClient
    from context_loader import ContextLoader
    from yaml_parser import extract_yaml_from_response, parse_frontmatter
    from response_parser import ResponseParser

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
        self.llm = LLMClient(vault_root=vault_root, system_instruction=SYSTEM_PROMPT)
        self.loader = ContextLoader(vault_root)
        self.parser = ResponseParser()
    
    def _extract_instructions(self, content: str) -> tuple:
        """
        Extracts LLM-Instructions block from note content.
        
        Args:
            content: Raw note content
            
        Returns:
            tuple: (instructions, cleaned_body) or (None, content) if no instructions
        """
        pattern = r'```LLM-Instructions\s*(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            instructions = match.group(1).strip()
            cleaned_body = re.sub(pattern, "", content, flags=re.DOTALL).strip()
            return instructions, cleaned_body
        return None, content
    
    def process_note(self, note_content: str) -> str:
        """
        Processes a note with instructions and generates a multi-file proposal.
        
        Args:
            note_content: The raw note content to analyze (may contain instruction block)
            
        Returns:
            str: Complete proposal note with frontmatter and sections
            
        Raises:
            Exception: If LLM call fails or parsing fails
        """
        # 1. Extract instructions and body
        instructions, body = self._extract_instructions(note_content)
        if not instructions:
            instructions = "Organize this note using standard conventions."
        
        # 2. Get full context (includes skeleton)
        context = self.loader.get_full_context()
        
        # 3. Get skeleton directly from indexer (for separate passing to LLM)
        skeleton = self.loader.indexer.build_skeleton()
        
        # 4. Generate proposal using architect prompt
        llm_response = self.llm.generate_proposal(instructions, body, context, skeleton)
        
        # 5. Parse response to extract files
        parsed = self.parser.parse(llm_response)
        
        # 6. Extract file paths and folders
        file_paths = [f['path'] for f in parsed['files']]
        folders = list(set([str(Path(p).parent) for p in file_paths if p]))
        
        # 7. Construct proposal note frontmatter
        frontmatter_dict = {
            'folders-to-create': folders,
            'files-to-create': file_paths,
            'librarian': 'review'
        }
        
        # 8. Build proposal note content
        proposal_content = f"""%%INSTRUCTIONS%%
{instructions}
---
%%ORIGINAL%%
{body}
---
{llm_response}
"""
        
        # 9. Create frontmatter Post and return as string
        proposal_note = frontmatter.Post(proposal_content, **frontmatter_dict)
        return frontmatter.dumps(proposal_note)
