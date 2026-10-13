import asyncio
import logging
import os
import signal
from datetime import timedelta
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker
from hello.activities import greet
from hello.workflows import HelloWorkflow

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "temporal-frontend:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    async with Worker(
        client,
        task_queue="hello-world",
        workflows=[HelloWorkflow],
        activities=[greet],
        max_concurrent_activities=2,
        max_concurrent_workflow_tasks=2,
        graceful_shutdown_timeout=timedelta(seconds=10),
    ):
        Path("/tmp/worker-ready").touch()
        logging.info("Worker connected; polling hello-world")
        await stop.wait()

if __name__ == "__main__":
    asyncio.run(main())
