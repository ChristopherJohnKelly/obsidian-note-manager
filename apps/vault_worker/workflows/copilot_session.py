from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.vault_worker.activities.llm import generate_chat_response
    from apps.vault_worker.core.react_parser import parse_react_response
    from packages.shared.workflow_names import (
        QRY_GET_HISTORY,
        QRY_GET_STATUS,
        SIG_CANCEL_SESSION,
        SIG_RECEIVE_MESSAGE,
    )


@workflow.defn
class CopilotSessionWorkflow:
    def __init__(self) -> None:
        self._history: list[dict] = []
        self._pending: list[dict] = []
        self._status: str = "idle"
        self._cancelled: bool = False

    @workflow.run
    async def run(self, input: dict) -> None:
        while not self._cancelled:
            await workflow.wait_condition(lambda: bool(self._pending) or self._cancelled)
            if self._cancelled:
                break
            msg = self._pending.pop(0)
            await self._run_react_iteration(msg, input)
        self._status = "complete"

    @workflow.signal(name=SIG_RECEIVE_MESSAGE)
    def receive_message(self, message: dict) -> None:
        self._pending.append(message)

    @workflow.signal(name=SIG_CANCEL_SESSION)
    def cancel_session(self) -> None:
        self._cancelled = True

    @workflow.query(name=QRY_GET_HISTORY)
    def get_history(self) -> list[dict]:
        return self._history

    @workflow.query(name=QRY_GET_STATUS)
    def get_status(self) -> str:
        return self._status

    async def _run_react_iteration(self, msg: dict, input: dict) -> None:
        self._status = "thinking"
        self._history.append(msg)
        raw: str = await workflow.execute_activity(
            generate_chat_response,
            args=[self._history],
            schedule_to_close_timeout=timedelta(minutes=2),
        )
        parse_react_response(raw)
        self._history.append({"role": "assistant", "content": raw})
        self._status = "idle"
