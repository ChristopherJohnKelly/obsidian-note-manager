"""Parse LLM fix output into a clean body string."""

from __future__ import annotations

import frontmatter

from apps.vault_worker.core.response_parser import parse_llm_response


def parse_fix(raw: str) -> str | None:
    """Extract body from a %%FILE%%...%%END%% LLM response block.

    Uses parse_llm_response to extract the first file block, then
    python-frontmatter to safely strip the YAML fence from the content.

    Returns:
        Non-empty body string, or None if no block found or body is empty.
        Never returns an empty string.
    """
    blocks = parse_llm_response(raw)
    if not blocks:
        return None
    content = blocks[0]["content"]
    post = frontmatter.loads(content)
    body = (post.content or "").strip()
    return body or None
