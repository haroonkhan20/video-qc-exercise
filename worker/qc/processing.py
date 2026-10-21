"""Safe processing diagnostics; messages and payloads are never copied into reports."""
def failure(stage, error, stream=""):
    """Describe a failed activity using allowlisted structural fields only."""
    cause = error
    seen = set()
    while getattr(cause, "cause", None) is not None and id(cause) not in seen:
        seen.add(id(cause))
        cause = cause.cause
    # ApplicationError.type carries the originating activity exception type.
    if type(cause).__name__ == "CancelledError":raise cause
    category = getattr(cause, "type", None) or type(cause).__name__
    category = str(category)
    if not category.replace("_", "").isalnum() or len(category) > 80:
        category = "ProcessingError"
    return {"stage": stage, "stream": str(stream), "error_type": category,
            "reason_code": "CHECK_UNAVAILABLE",
            "explanation": "Checking could not finish. This does not prove the recording is damaged."}

def status(errors):
    return {"processing_status": "incomplete" if errors else "complete",
            "processing_errors": errors}

def unavailable_movement():
    def item():
        return {"status":"not_assessed","severity":"not_assessed","findings":[],"streams":[]}
    return {"head_motion":item(),"hand_motion":item()}
