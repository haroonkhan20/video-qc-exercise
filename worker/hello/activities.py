from temporalio import activity

@activity.defn
async def greet(name: str) -> str:
    message = f"Hello, {name}!"
    # External side effects belong in activities, which Temporal can retry.
    activity.logger.info(message)
    return message
