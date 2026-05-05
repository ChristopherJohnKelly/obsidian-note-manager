"""LLM Generation Activities for Temporal vault-worker.

All Activities are synchronous def functions — Temporal runs them in a
ThreadPoolExecutor automatically. The Gemini synchronous client makes a
blocking network call that can take several seconds. Do not convert to async def.

Retry policies are defined here as module-level constants so downstream
Workflows can import and apply them at execute_activity() call site.
Do NOT pass retry policies to @activity.defn — that decorator does not accept them.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity
from temporalio.common import RetryPolicy

from apps.vault_worker.activities.llm_provider import LLMProviderBase
from packages.shared.models import ChatMessage, VaultContext, VaultNote

# ---------------------------------------------------------------------------
# Retry policy — import and apply at execute_activity() call site in Workflows
# ---------------------------------------------------------------------------

LLM_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    non_retryable_error_types=["ValueError"],
)

# ---------------------------------------------------------------------------
# Provider injection — swapped by tests via configure_provider()
# ---------------------------------------------------------------------------

_provider: LLMProviderBase | None = None


def configure_provider(provider: LLMProviderBase | None) -> None:
    """Inject the LLM provider used by Activities.

    Call this before registering Activities with the Worker:
    - Production: configure_provider(GeminiProvider())
    - Tests: configure_provider(FakeLLMProvider())
    """
    global _provider
    _provider = provider


def _get_provider() -> LLMProviderBase:
    if _provider is None:
        raise RuntimeError(
            "LLM provider not configured. "
            "Call configure_provider(provider) before running LLM Activities."
        )
    return _provider


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
def generate_chat_response(messages: list[ChatMessage]) -> str:
    provider = _get_provider()
    return provider.generate_chat_response(messages)


@activity.defn
def generate_proposal(context: VaultContext, source_body: str) -> str:
    """Generate a filing proposal for an inbox note.

    Returns raw LLM response with %%FILE%%...%%END%% markers.

    Synchronous def: Temporal runs this in a ThreadPoolExecutor automatically.
    The LLM provider makes a blocking network call — do not use async def.
    Retry policy is applied by the calling Workflow via execute_activity(), not here.
    """
    provider = _get_provider()
    instructions = (
        "File this inbox note into the correct vault location. "
        "Choose the most appropriate project or area based on the content."
    )
    context_str = (
        f"Context code: {context.context_code}\n"
        f"Code registry:\n{context.code_registry}"
    )
    return provider.generate_proposal(
        instructions=instructions,
        body=source_body,
        context=context_str,
        skeleton=context.skeleton,
    )


@activity.defn
def generate_fix(note: VaultNote, reasons: list[str], context: VaultContext) -> str:
    """Generate a fix proposal for a Night Watchman violation.

    Returns raw LLM response with %%FILE%%...%%END%% markers.

    Synchronous def — see generate_proposal docstring for rationale.
    """
    provider = _get_provider()
    violations = ", ".join(reasons)
    instructions = (
        f"Fix the following quality violations in this note: {violations}. "
        f"The note is at: {note.path}"
    )
    context_str = (
        f"Context code: {context.context_code}\n"
        f"Code registry:\n{context.code_registry}"
    )
    return provider.generate_fix(
        instructions=instructions,
        body=note.body,
        context=context_str,
        skeleton=context.skeleton,
    )
