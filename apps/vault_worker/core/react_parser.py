import json
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectResponse:
    content: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict


def parse_react_response(raw: str) -> DirectResponse | ToolCall:
    if not raw.lstrip().startswith("TOOL:"):
        return DirectResponse(raw)

    lines = raw.splitlines()
    name = ""
    args = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TOOL:"):
            name = stripped[len("TOOL:"):].strip()
        elif stripped.startswith("ARGS:"):
            args_str = stripped[len("ARGS:"):].strip()
            if args_str:
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}

    return ToolCall(name=name, args=args)
