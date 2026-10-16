"""Combined display status without changing immutable automatic reports."""
def combined_verdict(original,*evidence):
    states=[e.get("severity") for e in evidence if e]
    if original=="fail" or "fail" in states:return "fail"
    if original=="needs_review" or any(s in {"review","not_assessed"} for s in states):return "needs_review"
    return original
