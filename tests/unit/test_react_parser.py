"""Tests for react_parser module."""
import pytest
from apps.vault_worker.core.react_parser import DirectResponse, ToolCall, parse_react_response


class TestParseReactResponse:
    """Test suite for parse_react_response function."""

    def test_parse_direct_response_simple_text(self):
        """Plain text without TOOL: prefix returns DirectResponse."""
        result = parse_react_response("Hello, here's your answer.")
        assert isinstance(result, DirectResponse)
        assert result.content == "Hello, here's your answer."

    def test_parse_tool_call_with_empty_args(self):
        """TOOL: prefix with empty ARGS returns ToolCall with empty dict."""
        result = parse_react_response("TOOL: get_skeleton\nARGS: {}")
        assert isinstance(result, ToolCall)
        assert result.name == "get_skeleton"
        assert result.args == {}

    def test_parse_tool_call_with_json_args(self):
        """TOOL: prefix with JSON ARGS returns ToolCall with parsed args."""
        result = parse_react_response('TOOL: get_code_registry\nARGS: {"k": "v"}')
        assert isinstance(result, ToolCall)
        assert result.name == "get_code_registry"
        assert result.args == {"k": "v"}

    def test_no_tool_prefix_returns_direct_response(self):
        """Response without TOOL: prefix is always DirectResponse."""
        result = parse_react_response("This is a response with ARGS: something in it")
        assert isinstance(result, DirectResponse)
        assert result.content == "This is a response with ARGS: something in it"

    def test_tool_without_args_line_defaults_to_empty_dict(self):
        """TOOL: prefix without ARGS line defaults args to {}."""
        result = parse_react_response("TOOL: some_tool")
        assert isinstance(result, ToolCall)
        assert result.name == "some_tool"
        assert result.args == {}

    def test_direct_response_is_frozen(self):
        """DirectResponse is a frozen dataclass."""
        response = DirectResponse(content="test")
        with pytest.raises(AttributeError):
            response.content = "modified"

    def test_tool_call_is_frozen(self):
        """ToolCall is a frozen dataclass."""
        tool_call = ToolCall(name="test", args={})
        with pytest.raises(AttributeError):
            tool_call.name = "modified"
