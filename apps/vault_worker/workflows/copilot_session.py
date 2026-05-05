from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.llm import generate_chat_response
    from apps.vault_worker.core.react_parser import (
        DirectResponse,
        ToolCall,
        parse_react_response,
    )
    from packages.shared.workflow_names import (
        QRY_GET_HISTORY,
        QRY_GET_STATUS,
        SIG_CANCEL_SESSION,
        SIG_RECEIVE_MESSAGE,
    )


@dataclass
class CopilotSessionInput:
    vault_path: str
    session_id: str


@workflow.defn
class CopilotSessionWorkflow:
    def __init__(self) -> None:
        self._history: list[dict] = []
        self._pending_messages: list[dict] = []
        self._cancelled: bool = False
        self._status: str = "idle"

    @workflow.signal(name=SIG_RECEIVE_MESSAGE)
    def receive_message(self, message: dict) -> None:
        self._pending_messages.append(message)

    @workflow.signal(name=SIG_CANCEL_SESSION)
    def cancel_session(self) -> None:
        self._cancelled = True

    @workflow.query(name=QRY_GET_HISTORY)
    def get_history(self) -> list[dict]:
        return list(self._history)

    @workflow.query(name=QRY_GET_STATUS)
    def get_status(self) -> str:
        return self._status

    @workflow.run
    async def run(self, input: CopilotSessionInput) -> None:
        while not self._cancelled:
            await workflow.wait_condition(
                lambda: bool(self._pending_messages) or self._cancelled
            )
            if self._cancelled:
                break
            msg = self._pending_messages.pop(0)
            await self._run_react_iteration(msg, input.vault_path)
        self._status = "complete"

    async def _run_react_iteration(self, user_msg: dict, vault_path: str) -> None:
        self._status = "thinking"
        self._history.append(user_msg)
        raw = await workflow.execute_activity(
            generate_chat_response,
            args=[self._history],
            schedule_to_close_timeout=timedelta(minutes=2),
        )
        parsed = parse_react_response(raw)
        if isinstance(parsed, ToolCall):
            raise RuntimeError("Tool dispatch lands in C3 — not yet implemented")
        self._history.append({"role": "assistant", "content": parsed.content})
        self._status = "idle"
