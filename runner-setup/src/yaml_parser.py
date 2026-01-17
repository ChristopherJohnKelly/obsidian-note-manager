import re
import yaml
from typing import Dict, Optional


def extract_yaml_from_response(response: str) -> Optional[str]:
    """
    Extracts YAML content from LLM response.
    Handles both markdown code blocks (```yaml ... ```) and YAML frontmatter (---yaml ... ---).
    
    Args:
        response: Raw response string from LLM
        
    Returns:
        Optional[str]: Extracted YAML content, or None if not found
    """
    # Try to find YAML in markdown code blocks first
    yaml_block_pattern = r'```(?:yaml)?\s*\n(.*?)```'
    match = re.search(yaml_block_pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try to find YAML frontmatter format (---yaml ... ---)
    yaml_frontmatter_pattern = r'---yaml\s*\n(.*?)---'
    match = re.search(yaml_frontmatter_pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try to find plain YAML frontmatter (--- ... ---)
    plain_frontmatter_pattern = r'^---\s*\n(.*?)---\s*$'
    match = re.search(plain_frontmatter_pattern, response, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # If no code blocks found, try to parse the entire response as YAML
    # (in case LLM returned raw YAML without formatting)
    response_stripped = response.strip()
    if response_stripped.startswith('---'):
        # Remove leading --- if present
        response_stripped = re.sub(r'^---\s*\n?', '', response_stripped)
        response_stripped = re.sub(r'\n?---\s*$', '', response_stripped)
    
    return response_stripped if response_stripped else None


def parse_frontmatter(yaml_content: str) -> Dict:
    """
    Validates and parses YAML content into a dictionary.
    
    Args:
        yaml_content: YAML string to parse
        
    Returns:
        Dict: Parsed YAML as dictionary
        
    Raises:
        yaml.YAMLError: If YAML is malformed
        ValueError: If yaml_content is empty or None
    """
    if not yaml_content:
        raise ValueError("YAML content is empty")
    
    try:
        parsed = yaml.safe_load(yaml_content)
        if parsed is None:
            return {}
        return parsed
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML: {e}") from e
