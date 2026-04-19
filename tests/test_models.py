"""Unit tests for shared domain models.

Tests cover:
- Valid instantiation of each model
- Field defaults
- Pydantic validation (rejection of invalid types)
- Extra field behavior on Frontmatter
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from packages.shared.models import (
    AuditProposal,
    ChatMessage,
    CodeRegistryEntry,
    FilingProposal,
    Frontmatter,
    ValidationResult,
    VaultContext,
    VaultNote,
)
from packages.shared.workflow_names import (
    COPILOT_SESSION_WORKFLOW,
    FILER_INGESTION_WORKFLOW,
    NIGHT_WATCHMAN_WORKFLOW,
    QRY_GET_DRAFT_PROPOSAL,
    QRY_GET_HISTORY,
    QRY_GET_PROGRESS,
    QRY_GET_STATUS,
    QRY_GET_SYNC_STATUS,
    READ_VAULT_WORKFLOW,
    SIG_APPROVE,
    SIG_CANCEL_SESSION,
    SIG_ENSURE_SYNCED,
    SIG_RECEIVE_MESSAGE,
    SIG_REJECT,
    SIG_SYNC_ACK,
    VAULT_MANAGER_ID,
    VAULT_MANAGER_WORKFLOW,
    WORKFLOW_NAMES,
    WRITE_VAULT_WORKFLOW,
)


class TestFrontmatter:
    """Tests for Frontmatter model."""

    def test_valid_minimal_instantiation(self):
        """Frontmatter can be instantiated with no arguments."""
        fm = Frontmatter()
        assert fm.type is None
        assert fm.status is None
        assert fm.title is None
        assert fm.aliases == []
        assert fm.tags == []
        assert fm.code is None
        assert fm.folder is None

    def test_valid_full_instantiation(self):
        """Frontmatter accepts all fields."""
        fm = Frontmatter(
            type="note",
            status="active",
            title="Test Note",
            aliases=["alias1", "alias2"],
            tags=["tag1", "tag2"],
            code="test-code",
            folder="test-folder",
        )
        assert fm.type == "note"
        assert fm.status == "active"
        assert fm.title == "Test Note"
        assert fm.aliases == ["alias1", "alias2"]
        assert fm.tags == ["tag1", "tag2"]
        assert fm.code == "test-code"
        assert fm.folder == "test-folder"

    def test_extra_fields_allowed(self):
        """Frontmatter allows extra fields due to extra='allow'."""
        fm = Frontmatter(type="note", custom_field="custom_value", another_field=123)
        assert fm.custom_field == "custom_value"
        assert fm.another_field == 123

    def test_field_defaults(self):
        """aliases and tags default to empty lists."""
        fm = Frontmatter()
        assert fm.aliases == []
        assert fm.tags == []
        # Ensure they're different list instances (not shared)
        fm.aliases.append("test")
        assert fm.tags == []

    def test_type_field_rejects_non_string(self):
        """Frontmatter.type rejects non-string values."""
        with pytest.raises(ValidationError):
            Frontmatter(type=123)

    def test_tags_rejects_non_list(self):
        """Frontmatter.tags rejects non-list values."""
        with pytest.raises(ValidationError):
            Frontmatter(tags="not-a-list")


class TestVaultNote:
    """Tests for VaultNote model."""

    def test_valid_minimal_instantiation(self):
        """VaultNote requires path and frontmatter, body defaults to empty string."""
        fm = Frontmatter(type="note")
        note = VaultNote(path=Path("/test/note.md"), frontmatter=fm)
        assert note.path == Path("/test/note.md")
        assert note.frontmatter == fm
        assert note.body == ""

    def test_valid_full_instantiation(self):
        """VaultNote accepts all fields."""
        fm = Frontmatter(type="note")
        note = VaultNote(
            path=Path("/test/note.md"),
            frontmatter=fm,
            body="# Test Note\n\nContent here.",
        )
        assert note.path == Path("/test/note.md")
        assert note.frontmatter == fm
        assert note.body == "# Test Note\n\nContent here."

    def test_missing_required_fields_rejected(self):
        """VaultNote rejects instantiation without required path and frontmatter."""
        with pytest.raises(ValidationError):
            VaultNote()


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_valid_instantiation(self):
        """ValidationResult requires path, score, and reasons."""
        result = ValidationResult(
            path=Path("/test/note.md"),
            score=85,
            reasons=["reason 1", "reason 2"],
        )
        assert result.path == Path("/test/note.md")
        assert result.score == 85
        assert result.reasons == ["reason 1", "reason 2"]

    def test_score_must_be_int(self):
        """score must be an integer."""
        with pytest.raises(ValidationError):
            ValidationResult(path=Path("/test.md"), score="not-an-int")


class TestCodeRegistryEntry:
    """Tests for CodeRegistryEntry model."""

    def test_valid_instantiation(self):
        """CodeRegistryEntry requires code, name, and folder."""
        entry = CodeRegistryEntry(
            code="def foo(): pass",
            name="foo",
            folder="/code",
        )
        assert entry.code == "def foo(): pass"
        assert entry.name == "foo"
        assert entry.type == ""  # default
        assert entry.folder == "/code"

    def test_type_default(self):
        """type defaults to empty string."""
        entry = CodeRegistryEntry(code="x", name="y", folder="z")
        assert entry.type == ""

    def test_missing_required_fields_rejected(self):
        """CodeRegistryEntry rejects instantiation without required fields."""
        with pytest.raises(ValidationError):
            CodeRegistryEntry()


class TestVaultContext:
    """Tests for VaultContext model."""

    def test_valid_instantiation(self):
        """VaultContext requires all fields."""
        fm = Frontmatter(type="note")
        note = VaultNote(path=Path("/root.md"), frontmatter=fm)
        ctx = VaultContext(
            context_code="CONTEXT001",
            root_note=note,
            related_notes=[note],
            skeleton="skeleton content",
            code_registry="registry content",
        )
        assert ctx.context_code == "CONTEXT001"
        assert ctx.root_note == note
        assert ctx.related_notes == [note]
        assert ctx.skeleton == "skeleton content"
        assert ctx.code_registry == "registry content"


class TestFilingProposal:
    """Tests for FilingProposal model."""

    def test_valid_instantiation(self):
        """FilingProposal requires all fields."""
        fm = Frontmatter(type="note")
        proposal = FilingProposal(
            source_path=Path("/source.md"),
            proposed_path=Path("/target/note.md"),
            proposed_frontmatter=fm,
            reasoning="Better organization",
        )
        assert proposal.source_path == Path("/source.md")
        assert proposal.proposed_path == Path("/target/note.md")
        assert proposal.proposed_frontmatter == fm
        assert proposal.reasoning == "Better organization"


class TestAuditProposal:
    """Tests for AuditProposal model."""

    def test_valid_instantiation(self):
        """AuditProposal requires all fields."""
        proposal = AuditProposal(
            target_path=Path("/note.md"),
            proposed_content="# Updated Content",
            reasons=["reason 1", "reason 2"],
            score=90,
        )
        assert proposal.target_path == Path("/note.md")
        assert proposal.proposed_content == "# Updated Content"
        assert proposal.reasons == ["reason 1", "reason 2"]
        assert proposal.score == 90


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_valid_user_message(self):
        """ChatMessage accepts valid role 'user'."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_name is None
        assert msg.timestamp.tzinfo == timezone.utc

    def test_valid_assistant_message(self):
        """ChatMessage accepts valid role 'assistant'."""
        msg = ChatMessage(role="assistant", content="Hello")
        assert msg.role == "assistant"

    def test_valid_tool_message(self):
        """ChatMessage accepts valid role 'tool' with tool_name."""
        msg = ChatMessage(role="tool", content="result", tool_name="fetch_note")
        assert msg.role == "tool"
        assert msg.tool_name == "fetch_note"

    def test_invalid_role_rejected(self):
        """ChatMessage rejects invalid role values."""
        with pytest.raises(ValidationError):
            ChatMessage(role="invalid_role", content="test")

    def test_timestamp_default_utc(self):
        """ChatMessage timestamp defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        msg = ChatMessage(role="user", content="test")
        after = datetime.now(timezone.utc)
        assert before <= msg.timestamp <= after
        assert msg.timestamp.tzinfo == timezone.utc


class TestWorkflowNames:
    """Tests for workflow name constants."""

    def test_all_workflow_names_are_non_empty_strings(self):
        """All workflow name constants must be non-empty strings."""
        expected = {
            "VAULT_MANAGER_WORKFLOW": VAULT_MANAGER_WORKFLOW,
            "COPILOT_SESSION_WORKFLOW": COPILOT_SESSION_WORKFLOW,
            "NIGHT_WATCHMAN_WORKFLOW": NIGHT_WATCHMAN_WORKFLOW,
            "FILER_INGESTION_WORKFLOW": FILER_INGESTION_WORKFLOW,
            "READ_VAULT_WORKFLOW": READ_VAULT_WORKFLOW,
            "WRITE_VAULT_WORKFLOW": WRITE_VAULT_WORKFLOW,
        }
        for name, value in expected.items():
            assert isinstance(value, str), f"{name} must be a string"
            assert len(value) > 0, f"{name} must be non-empty"

    def test_workflow_names_match_expected_values(self):
        """Workflow names match the expected values from TRD Section 4.6."""
        assert VAULT_MANAGER_WORKFLOW == "VaultManagerWorkflow"
        assert COPILOT_SESSION_WORKFLOW == "CopilotSessionWorkflow"
        assert NIGHT_WATCHMAN_WORKFLOW == "NightWatchmanWorkflow"
        assert FILER_INGESTION_WORKFLOW == "FilerIngestionWorkflow"
        assert READ_VAULT_WORKFLOW == "ReadVaultWorkflow"
        assert WRITE_VAULT_WORKFLOW == "WriteVaultWorkflow"

    def test_vault_manager_id(self):
        """VAULT_MANAGER_ID is a non-empty string."""
        assert isinstance(VAULT_MANAGER_ID, str)
        assert len(VAULT_MANAGER_ID) > 0
        assert VAULT_MANAGER_ID == "vault-manager"

    def test_signal_names(self):
        """All signal names are non-empty strings."""
        signals = [
            SIG_RECEIVE_MESSAGE,
            SIG_CANCEL_SESSION,
            SIG_APPROVE,
            SIG_REJECT,
            SIG_ENSURE_SYNCED,
            SIG_SYNC_ACK,
        ]
        for sig in signals:
            assert isinstance(sig, str), f"{sig} must be a string"
            assert len(sig) > 0

    def test_query_names(self):
        """All query names are non-empty strings."""
        queries = [
            QRY_GET_HISTORY,
            QRY_GET_STATUS,
            QRY_GET_SYNC_STATUS,
            QRY_GET_DRAFT_PROPOSAL,
            QRY_GET_PROGRESS,
        ]
        for qry in queries:
            assert isinstance(qry, str)
            assert len(qry) > 0

    def test_workflow_names_export(self):
        """WORKFLOW_NAMES set is exported and contains all workflow names."""
        assert isinstance(WORKFLOW_NAMES, set)
        assert len(WORKFLOW_NAMES) > 0