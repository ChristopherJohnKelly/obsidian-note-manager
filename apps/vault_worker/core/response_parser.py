"""Parser for LLM output using %%FILE%%...%%END%% markers.

Migrated/rewritten from src_v2 to handle the new %%FILE%%/%%END%% format
used by vault-worker Activities. The src_v2 parser handled %%FILE: path%%
format; this parser handles the structured %%FILE%%\\npath: <path>\\n...%%END%% format.
"""

from __future__ import annotations

import re
from typing import TypedDict


class ParsedFile(TypedDict):
    """A single file block extracted from LLM output."""

    path: str
    content: str


def parse_llm_response(text: str) -> list[ParsedFile]:
    """Parse LLM output into a list of file blocks.

    Expected format per block:
        %%FILE%%
        path: <vault-relative-path>.md
        ---
        <frontmatter YAML>
        ---
        <body content>
        %%END%%

    Args:
        text: Raw LLM response containing one or more %%FILE%%...%%END%% blocks.

    Returns:
        List of ParsedFile dicts with 'path' and 'content' keys.
        'content' includes everything after the path line (frontmatter + body).
    """
    files: list[ParsedFile] = []

    if not text or not text.strip():
        return files

    # Match each %%FILE%%...%%END%% block (non-greedy, DOTALL)
    pattern = re.compile(r"%%FILE%%\n(.*?)%%END%%", re.DOTALL)
    for match in pattern.finditer(text):
        block = match.group(1)  # Everything between %%FILE%%\n and %%END%%

        # Extract path from first line: "path: <path>"
        lines = block.split("\n")
        path: str | None = None
        path_line_idx = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("path:"):
                path = stripped[len("path:"):].strip()
                path_line_idx = idx
                break

        if not path:
            continue

        # Content is everything after the path line
        content_lines = lines[path_line_idx + 1:]
        content = "\n".join(content_lines).strip()

        files.append({"path": path, "content": content})

    return files
