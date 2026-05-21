from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class DirectResponse:
    content: str


@dataclass
class ToolCall:
    tool_name: str
    args: dict = field(default_factory=dict)


def parse_react_response(text: str) -> DirectResponse | ToolCall:
    lines = text.split("\n")
    first_non_empty = next((l for l in lines if l.strip()), "")

    tool_match = re.match(r"^TOOL:\s*(\S+)\s*$", first_non_empty)
    if not tool_match:
        return DirectResponse(content=text.strip())

    tool_name = tool_match.group(1)

    args: dict = {}
    args_match = re.search(r"^ARGS:\s*(.*)", text, re.MULTILINE)
    if args_match:
        raw = args_match.group(1).strip()
        if raw:
            args = json.loads(raw)

    return ToolCall(tool_name=tool_name, args=args)
