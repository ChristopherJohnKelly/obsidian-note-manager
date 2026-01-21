import re


class ResponseParser:
    def parse(self, text: str) -> dict:
        """
        Parses the LLM output blob into structured data.
        Expected format:
        %%EXPLANATION%%
        ... text ...
        %%FILE: path/to/file.md%%
        ... content ...
        
        Args:
            text: Raw LLM response text
            
        Returns:
            dict: Parsed structure with 'explanation' and 'files' keys
        """
        result = {
            "explanation": "",
            "files": []
        }
        
        if not text or not text.strip():
            return result
        
        # Normalize: remove %%EXPLANATION%% marker if present
        normalized_text = text.replace("%%EXPLANATION%%", "").strip()
        
        # Split by %%FILE: markers
        parts = re.split(r'%%FILE:\s*', normalized_text)
        
        if len(parts) == 1:
            # No file markers found - entire text is explanation
            result["explanation"] = normalized_text.strip()
            return result
        
        # First part is explanation (text before first %%FILE:)
        result["explanation"] = parts[0].strip()
        
        # Process remaining parts (file blocks)
        for part in parts[1:]:
            if not part.strip():
                continue  # Skip empty blocks
            
            # Extract path (until %% or newline or end)
            path_match = re.match(r'^([^\n%]+?)(?:%%|$)', part)
            if not path_match:
                # Malformed marker - skip with warning
                print(f"⚠️ Warning: Malformed file marker, skipping block")
                continue
            
            path = path_match.group(1).strip()
            
            # Extract content (everything after path until next marker or end)
            # Remove the path line from the content
            content_start = path_match.end()
            if path_match.group(0).endswith('%%'):
                # Path had closing %%, skip it
                content_start = part.find('%%', path_match.start()) + 2
            
            content = part[content_start:].strip()
            
            result["files"].append({
                "path": path,
                "content": content
            })
        
        return result
