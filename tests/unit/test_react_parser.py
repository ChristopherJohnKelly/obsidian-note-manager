import pytest
from apps.vault_worker.core.react_parser import (
    DirectResponse,
    ToolCall,
    parse_react_response,
)


class TestParseReactResponse:
    """Test the pure parser that splits LLM output into DirectResponse or ToolCall."""

    def test_parse_tool_call_with_empty_args(self):
        """Parse a tool call with empty ARGS."""
        text = "TOOL: get_skeleton\nARGS: {}"
        result = parse_react_response(text)

        assert isinstance(result, ToolCall)
        assert result.tool_name == "get_skeleton"
        assert result.args == {}

    def test_parse_tool_call_with_json_args(self):
        """Parse a tool call with populated JSON args."""
        text = 'TOOL: search\nARGS: {"query": "python", "limit": 5}'
        result = parse_react_response(text)

        assert isinstance(result, ToolCall)
        assert result.tool_name == "search"
        assert result.args == {"query": "python", "limit": 5}

    def test_parse_tool_call_with_missing_args(self):
        """Parse a tool call where ARGS line is absent; default to {}."""
        text = "TOOL: list_files"
        result = parse_react_response(text)

        assert isinstance(result, ToolCall)
        assert result.tool_name == "list_files"
        assert result.args == {}

    def test_parse_tool_call_with_blank_args(self):
        """Parse a tool call where ARGS line is blank; default to {}."""
        text = "TOOL: reset\nARGS:"
        result = parse_react_response(text)

        assert isinstance(result, ToolCall)
        assert result.tool_name == "reset"
        assert result.args == {}

    def test_parse_direct_response_plain_text(self):
        """Parse plain prose text as a DirectResponse."""
        text = "Here is a summary of your vault."
        result = parse_react_response(text)

        assert isinstance(result, DirectResponse)
        assert result.content == "Here is a summary of your vault."

    def test_parse_direct_response_multiline(self):
        """Parse multiline text as a DirectResponse; strip leading/trailing whitespace."""
        text = "  \nHere is a longer response\nwith multiple lines.  \n  "
        result = parse_react_response(text)

        assert isinstance(result, DirectResponse)
        assert result.content == "Here is a longer response\nwith multiple lines."

    def test_parse_direct_response_not_tool_format(self):
        """Plain text that happens to contain 'TOOL:' but not at line start is a DirectResponse."""
        text = "This mentions TOOL: but not in the expected format\nso it should be treated as prose."
        result = parse_react_response(text)

        assert isinstance(result, DirectResponse)
        assert "TOOL:" in result.content

    def test_tool_call_dataclass_has_tool_name_field(self):
        """ToolCall dataclass has tool_name field."""
        tc = ToolCall(tool_name="test", args={})
        assert hasattr(tc, "tool_name")
        assert tc.tool_name == "test"

    def test_tool_call_dataclass_has_args_field(self):
        """ToolCall dataclass has args field."""
        tc = ToolCall(tool_name="test", args={"key": "value"})
        assert hasattr(tc, "args")
        assert tc.args == {"key": "value"}

    def test_direct_response_dataclass_has_content_field(self):
        """DirectResponse dataclass has content field."""
        dr = DirectResponse(content="test content")
        assert hasattr(dr, "content")
        assert dr.content == "test content"
