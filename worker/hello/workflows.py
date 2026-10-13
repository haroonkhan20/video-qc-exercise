from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from hello.activities import greet

@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        # No files, network, random numbers, environment reads, or wall-clock time here.
        return await workflow.execute_activity(
            greet,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
