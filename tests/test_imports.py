"""Placeholder test to verify B1 foundation imports."""


def test_domain_models_import():
    """Verify domain models can be imported."""
    from src_v2.core.domain.models import Frontmatter, Link, Note, ValidationResult

    assert Note is not None
    assert Frontmatter is not None
    assert Link is not None
    assert ValidationResult is not None


def test_ports_import():
    """Verify port interfaces can be imported."""
    from src_v2.core.interfaces.ports import LLMProvider, VaultRepository

    assert VaultRepository is not None
    assert LLMProvider is not None
