"""Chat Service - Agent 1 (The Analyst). ReAct loop with read-only vault tools."""

import json
import os
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, GenerationConfig, Tool

from src_v2.core.interfaces.ports import VaultRepository

ANALYST_SYSTEM_PROMPT = """You are an Obsidian Analyst. Your role is to answer questions about the user's vault based solely on the files you read.

RULES:
1. You are restricted to the '{active_area}' directory. Use your tools to list and read files only within this area.
2. Always use list_files_in_area before reading to discover what files exist.
3. Ground your answers strictly in the content you retrieve. Do not invent or assume.
4. If a file is not found or the path is invalid, say so clearly.
5. You have read-only access. You cannot create, edit, or delete files."""

MAX_REACT_ITERATIONS = 10


def _resolve_path_within_area(
    active_area: str,
    relative_path: str,
    vault_root: Path,
) -> Path | None:
    """
    Resolve relative_path within active_area. Returns vault-relative Path or None if invalid.

    Prevents path traversal: rejects '..', leading slashes, and paths escaping active_area.
    """
    root = Path(vault_root).resolve()
    base = (root / active_area).resolve()
    if not relative_path or not relative_path.strip():
        return Path(active_area)
    path_str = relative_path.strip()
    if ".." in path_str or path_str.startswith("/"):
        return None
    try:
        full = (base / path_str).resolve()
        if not str(full).startswith(str(base)):
            return None
        return full.relative_to(root)
    except (ValueError, RuntimeError):
        return None


def _build_tools() -> list:
    """Build Gemini tool declarations for list_files_in_area and read_file_content."""
    return [
        Tool(
            function_declarations=[
                FunctionDeclaration(
                    name="list_files_in_area",
                    description="List markdown files in a directory within the active vault area. Use relative_path '.' or empty for the area root, or a subpath like 'ProjectName'.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "Path relative to the active area (e.g. '.' or '20. Projects/Pepsi')",
                            }
                        },
                        "required": ["relative_path"],
                    },
                ),
                FunctionDeclaration(
                    name="read_file_content",
                    description="Read the raw content of a markdown file within the active vault area.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "Path to the file relative to the active area (e.g. 'readme.md' or 'Pepsi/Overview.md')",
                            }
                        },
                        "required": ["relative_path"],
                    },
                ),
            ]
        )
    ]


class ChatService:
    """ReAct agent for conversational QA over the vault. Read-only tools only."""

    def __init__(
        self,
        repo: VaultRepository,
        *,
        vault_root: Path | None = None,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        self.repo = repo
        self.vault_root = vault_root or Path(os.getenv("OBSIDIAN_VAULT_ROOT", "."))
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY required for ChatService")
        genai.configure(api_key=key)
        self.model_name = model_name
        self._tools = _build_tools()

    def _list_files_in_area(self, active_area: str, relative_path: str) -> str:
        """List .md files in directory. Returns JSON array of paths or error message."""
        resolved = _resolve_path_within_area(active_area, relative_path, self.vault_root)
        if resolved is None:
            return json.dumps({"error": "Invalid or disallowed path (path traversal blocked)"})
        paths = self.repo.list_note_paths_in(resolved)
        return json.dumps([str(p) for p in paths])

    def _read_file_content(self, active_area: str, relative_path: str) -> str:
        """Read file content. Returns content or error message."""
        resolved = _resolve_path_within_area(active_area, relative_path, self.vault_root)
        if resolved is None:
            return json.dumps({"error": "Invalid or disallowed path (path traversal blocked)"})
        content = self.repo.read_raw(resolved)
        if content is None:
            return json.dumps({"error": f"File not found: {resolved}"})
        return content

    def _execute_tool(self, name: str, args: dict, active_area: str) -> str:
        """Execute a tool by name. Returns result string."""
        if name == "list_files_in_area":
            return self._list_files_in_area(
                active_area,
                args.get("relative_path", "."),
            )
        if name == "read_file_content":
            return self._read_file_content(
                active_area,
                args.get("relative_path", ""),
            )
        return json.dumps({"error": f"Unknown tool: {name}"})

    def chat(self, user_message: str, active_area: str) -> str:
        """
        Run ReAct loop: send user message, handle tool calls, return final text response.

        Args:
            user_message: User's question.
            active_area: Vault directory to scope tools to (e.g. "20. Projects").

        Returns:
            Final assistant text response.
        """
        system_instruction = ANALYST_SYSTEM_PROMPT.format(active_area=active_area)
        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=system_instruction,
            tools=self._tools,
        )
        chat = model.start_chat()
        config = GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )

        response = chat.send_message(user_message, generation_config=config)
        iterations = 0

        while iterations < MAX_REACT_ITERATIONS:
            iterations += 1
            parts = response.candidates[0].content.parts if response.candidates else []
            function_call = None
            text_parts = []

            for part in parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_call = part.function_call
                    break
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            if function_call:
                name = function_call.name
                args = dict(function_call.args) if function_call.args else {}
                result = self._execute_tool(name, args, active_area)
                from google.generativeai.protos import Content, FunctionResponse, Part

                try:
                    response_dict = json.loads(result) if result.startswith("{") else {"result": result}
                except json.JSONDecodeError:
                    response_dict = {"result": result}

                fr = FunctionResponse(name=name, response=response_dict)
                response = chat.send_message(
                    Content(role="user", parts=[Part(function_response=fr)]),
                    generation_config=config,
                )
                continue

            return "".join(text_parts) if text_parts else "I couldn't generate a response."

        return "Maximum tool-calling iterations reached. Please try a simpler question."
