"""Parse LLM fix output into a clean body string.

This function is total: it never raises, whatever the LLM returned.
NightWatchmanWorkflow calls it inside @workflow.run, where an escaped
exception becomes an infinite workflow-task retry loop — and a wrong
guess writes garbage over a vault note and pushes it. Any ambiguity
therefore resolves to None (skip the note), never to a raise or a leak.
"""

from __future__ import annotations

import re

import yaml

from apps.vault_worker.core.response_parser import parse_llm_response

# A leading frontmatter fence: '---' line, YAML, closing '---' line.
# Anchored at the very start — a '---' thematic break later in a body
# never matches.
_FENCE_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)


def parse_fix(raw: str) -> str | None:
    """Extract the body from a %%FILE%%...%%END%% LLM response block.

    Returns a non-empty body string, or None when the response should be
    skipped: no marker block, empty body, or any fence/YAML ambiguity.

    Fence handling:
    - A valid leading fence whose YAML parses to a mapping is stripped
      (the LLM included frontmatter; the workflow preserves the note's
      own frontmatter separately).
    - A leading fence whose YAML is malformed → None. Guessing here is
      how raw YAML leaked into note bodies.
    - Content that opens with '---' but has no closing fence
      (unterminated) → None.
    - A '---' pair that encloses non-mapping text is a pair of thematic
      breaks, not frontmatter: the content is kept verbatim.
    """
    try:
        blocks = parse_llm_response(raw)
    except Exception:
        return None
    if not blocks:
        return None
    content = blocks[0].get("content") or ""

    m = _FENCE_RE.match(content)
    if m:
        try:
            meta = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            return None
        if isinstance(meta, dict):
            body = content[m.end():].strip()
        else:
            # '---' ... '---' around prose: thematic breaks, keep verbatim.
            body = content.strip()
    elif content.lstrip().startswith("---"):
        # Opens like a fence but never closes: unterminated, unparseable.
        return None
    else:
        body = content.strip()

    return body or None
