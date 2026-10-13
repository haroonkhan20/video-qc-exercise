"""Deterministic orchestration: identifiers only, no filesystem/HTTP/clock/randomness."""
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

@workflow.defn
class QcEpisode:
    @workflow.run
    async def run(self, ref: dict) -> dict:
        options={"start_to_close_timeout":timedelta(minutes=30),
                 "heartbeat_timeout":timedelta(seconds=15),
                 "retry_policy":RetryPolicy(initial_interval=timedelta(seconds=2),
                                           maximum_interval=timedelta(seconds=20),maximum_attempts=5)}
        errors=[]
        try:
            inventory=await workflow.execute_activity("inspect_container",ref,result_type=dict,**options)
        except ActivityError:
            # Finalization must fail closed even if container inspection cannot complete.
            return await workflow.execute_activity("finalize_unavailable",ref,result_type=dict,**options)
        async def one(channel_id):
            try:
                return await workflow.execute_activity("check_stream",{"ref":ref,"channel_id":channel_id},
                                                        result_type=dict,**options)
            except ActivityError:
                return {"error":str(channel_id)}
        streams=await asyncio.gather(*(one(cid) for cid in sorted(inventory["stream_ids"])))
        errors.extend(s["error"] for s in streams if "error" in s)
        try:
            cross=await workflow.execute_activity("cross_stream",{"ref":ref,"streams":streams},result_type=dict,**options)
        except ActivityError:
            cross={};errors.append("cross_stream")
        return await workflow.execute_activity("finalize",{"ref":ref,"streams":streams,"cross":cross,"errors":errors},
                                               result_type=dict,**options)
