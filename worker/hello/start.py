import argparse
import asyncio
import json
import os
import uuid
from datetime import timedelta

from temporalio.client import Client, WorkflowExecutionStatus
from hello.workflows import HelloWorkflow

async def main(name: str) -> None:
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "temporal-frontend:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )
    # Random IDs are safe in a client script, outside replayed workflow code.
    handle = await client.start_workflow(
        HelloWorkflow.run,
        name,
        id=f"hello-{uuid.uuid4()}",
        task_queue="hello-world",
        execution_timeout=timedelta(minutes=2),
    )
    result = await asyncio.wait_for(handle.result(), timeout=150)
    description = await handle.describe()
    if description.status != WorkflowExecutionStatus.COMPLETED:
        raise RuntimeError(f"Unexpected status: {description.status}")
    print(json.dumps({
        "workflow_id": handle.id,
        "run_id": description.run_id,
        "status": description.status.name,
        "result": result,
    }))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="world")
    args = parser.parse_args()
    asyncio.run(main(args.name))
