"""Parser for LLM proposal output with %%FILE%% markers."""

import re
from typing import TypedDict


class ParsedFile(TypedDict):
    """A single file block from parsed LLM output."""

    path: str
    content: str


class ParsedProposal(TypedDict):
    """Parsed structure from LLM proposal response."""

    explanation: str
    files: list[ParsedFile]


def parse_proposal(text: str) -> ParsedProposal:
    """
    Parse the LLM output blob into structured data.

    Expected format:
        %%EXPLANATION%%
        ... text ...
        %%FILE: path/to/file.md%%
        ... content ...

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed structure with 'explanation' and 'files' keys.
    """
    result: ParsedProposal = {
        "explanation": "",
        "files": [],
    }

    if not text or not text.strip():
        return result

    normalized_text = text.replace("%%EXPLANATION%%", "").strip()
    parts = re.split(r"%%FILE:\s*", normalized_text)

    if len(parts) == 1:
        result["explanation"] = normalized_text.strip()
        return result

    result["explanation"] = parts[0].strip()

    for part in parts[1:]:
        if not part.strip():
            continue

        path_match = re.match(r"^([^\n%]+?)(?:%%|$)", part)
        if not path_match:
            continue

        path = path_match.group(1).strip()
        content_start = path_match.end()
        if path_match.group(0).endswith("%%"):
            content_start = part.find("%%", path_match.start()) + 2
        content = part[content_start:].strip()

        result["files"].append({"path": path, "content": content})

    return result
