"""Smoke test: proves WorkflowEnvironment works in-process without a live Temporal server."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.worker import Worker


@activity.defn
def ping_activity() -> str:
    return "pong"


@workflow.defn
class PingWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            ping_activity,
            schedule_to_close_timeout=timedelta(seconds=5),
        )


async def test_smoke(temporal_client):
    async with Worker(
        temporal_client,
        task_queue="test-queue",
        workflows=[PingWorkflow],
        activities=[ping_activity],
        activity_executor=ThreadPoolExecutor(max_workers=2),
    ):
        result = await temporal_client.execute_workflow(
            PingWorkflow.run, id="smoke-test", task_queue="test-queue"
        )
    assert result == "pong"
