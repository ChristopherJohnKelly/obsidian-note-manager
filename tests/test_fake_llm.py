"""Tests for FakeLLMProvider — determinism, interface, and response format."""
import pytest

from tests.mocks.fake_llm import FakeLLMProvider


@pytest.fixture
def fake_llm():
    return FakeLLMProvider()


class TestGenerateProposal:
    def test_returns_file_markers(self, fake_llm):
        result = fake_llm.generate_proposal(
            instructions="file this note",
            body="# Some Note\nContent.",
            context="vault context",
            skeleton="skeleton",
        )
        assert "%%FILE%%" in result
        assert "%%END%%" in result

    def test_returns_string(self, fake_llm):
        result = fake_llm.generate_proposal(
            instructions="inst", body="body", context="ctx", skeleton="skel"
        )
        assert isinstance(result, str)

    def test_determinism(self, fake_llm):
        args = dict(instructions="inst", body="body", context="ctx", skeleton="skel")
        first = fake_llm.generate_proposal(**args)
        second = fake_llm.generate_proposal(**args)
        assert first == second

    def test_contains_path(self, fake_llm):
        result = fake_llm.generate_proposal(
            instructions="inst", body="body", context="ctx", skeleton="skel"
        )
        assert "path:" in result

    def test_contains_frontmatter_yaml(self, fake_llm):
        result = fake_llm.generate_proposal(
            instructions="inst", body="body", context="ctx", skeleton="skel"
        )
        assert "aliases:" in result
        assert "tags:" in result


class TestGenerateFix:
    def test_returns_file_markers(self, fake_llm):
        result = fake_llm.generate_fix(
            instructions="fix this note",
            body="# Bad Note\nContent.",
            context="vault context",
            skeleton="skeleton",
        )
        assert "%%FILE%%" in result
        assert "%%END%%" in result

    def test_returns_string(self, fake_llm):
        result = fake_llm.generate_fix(
            instructions="inst", body="body", context="ctx", skeleton="skel"
        )
        assert isinstance(result, str)

    def test_determinism(self, fake_llm):
        args = dict(instructions="inst", body="body", context="ctx", skeleton="skel")
        first = fake_llm.generate_fix(**args)
        second = fake_llm.generate_fix(**args)
        assert first == second

    def test_contains_frontmatter_yaml(self, fake_llm):
        result = fake_llm.generate_fix(
            instructions="inst", body="body", context="ctx", skeleton="skel"
        )
        assert "aliases:" in result
        assert "tags:" in result

    def test_same_inputs_different_calls_same_output(self, fake_llm):
        """Verify determinism across separate provider instances."""
        provider1 = FakeLLMProvider()
        provider2 = FakeLLMProvider()
        args = dict(instructions="inst", body="body", context="ctx", skeleton="skel")
        assert provider1.generate_fix(**args) == provider2.generate_fix(**args)


class TestNotImplemented:
    def test_unimplemented_method_raises(self, fake_llm):
        """FakeLLMProvider must raise NotImplementedError on unimplemented methods."""
        with pytest.raises(NotImplementedError):
            fake_llm.generate_summary()  # type: ignore[attr-defined]
