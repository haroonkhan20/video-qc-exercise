import asyncio, logging, os, signal
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Worker
from qc.workflow import QcEpisode
from qc import storage as st
from qc.activities import inspect_container,check_stream,cross_stream,finalize,finalize_unavailable

async def main():
    logging.basicConfig(level=logging.INFO)
    client=await Client.connect(os.environ.get("TEMPORAL_ADDRESS","temporal-frontend:7233"),namespace="default")
    stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop.set)
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with Worker(client,task_queue="video-qc-"+st.code_version(),workflows=[QcEpisode],
                          activities=[inspect_container,check_stream,cross_stream,finalize,finalize_unavailable],
                          activity_executor=executor,max_concurrent_activities=1,max_concurrent_workflow_tasks=2,
                          graceful_shutdown_timeout=timedelta(seconds=10)):
            Path("/tmp/qc-worker-ready").touch()
            logging.info("QC worker polling video-qc")
            await stop.wait()
if __name__=="__main__":
    try:asyncio.run(main())
    finally:
        from qc import storage as st
        st.close_pool()
