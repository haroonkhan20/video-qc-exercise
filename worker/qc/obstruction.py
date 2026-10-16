"""Conservative, versioned screening of saved snapshots for dark edge blockage.

This is a review aid, not an object recognizer or a full-frame-video check.
"""
import hashlib
import io
from pathlib import Path

VERSION = "dark-edge-snapshots-v1"
SETTINGS = {"grid": 4, "dark_pixel": 20, "dark_fraction": .95,
            "tile_std_max": 6, "area_min": .20, "area_max": .75,
            "remaining_mean_min": 45, "remaining_std_min": 12,
            "minimum_seconds": 2, "minimum_samples": 3, "maximum_gap_seconds": 2.5}

def provenance():
    return {"version": VERSION, "source_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "settings": SETTINGS, "scope": "Saved snapshots, approximately one per second; not every frame. Dark edge blockages only."}

def inspect_image(data):
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        gray = np.asarray(image.convert("L").resize((160, 160)), dtype=float)
    dark = set()
    for y in range(4):
        for x in range(4):
            tile = gray[y*40:(y+1)*40, x*40:(x+1)*40]
            if (tile < SETTINGS["dark_pixel"]).mean() >= SETTINGS["dark_fraction"] and tile.std() <= SETTINGS["tile_std_max"]:
                dark.add((y, x))
    # Symmetric top/bottom or left/right bars are commonly normal letterboxing.
    if dark and (dark == {(y,x) for y in (0,3) for x in range(4)} or
                 dark == {(y,x) for x in (0,3) for y in range(4)}):
        return None
    remaining = set(dark)
    components = []
    while remaining:
        stack = [remaining.pop()]; component = set(stack)
        while stack:
            y,x = stack.pop()
            for point in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if point in remaining:
                    remaining.remove(point);component.add(point);stack.append(point)
        components.append(component)
    for component in sorted(components,key=len,reverse=True):
        area = len(component)/16
        if not SETTINGS["area_min"] <= area <= SETTINGS["area_max"]:continue
        if not any(y in (0,3) or x in (0,3) for y,x in component):continue
        mask = np.ones((160,160),dtype=bool)
        for y,x in dark:mask[y*40:(y+1)*40,x*40:(x+1)*40] = False
        rest = gray[mask]
        if not len(rest) or rest.mean() < SETTINGS["remaining_mean_min"] or rest.std() < SETTINGS["remaining_std_min"]:continue
        return {"area_fraction": area, "tiles": sorted([list(p) for p in component])}
    return None

def summarize(samples):
    """Samples are (relative seconds, JPEG bytes), with failures kept unknown."""
    checked = [];errors = 0
    for seconds,data in sorted(samples):
        try:checked.append({"seconds": seconds, "candidate": inspect_image(data)})
        except Exception:errors += 1
    runs = [];run = []
    def finish():
        if len(run) >= SETTINGS["minimum_samples"] and run[-1]["seconds"]-run[0]["seconds"] >= SETTINGS["minimum_seconds"]:
            runs.append({"start_s": run[0]["seconds"], "end_s": run[-1]["seconds"],
                         "samples": len(run), "maximum_area_fraction": max(s["candidate"]["area_fraction"] for s in run)})
    for sample in checked:
        adjacent = not run or (sample["seconds"]-run[-1]["seconds"] <= SETTINGS["maximum_gap_seconds"] and
                    set(map(tuple,sample["candidate"]["tiles"] if sample["candidate"] else [])) & set(map(tuple,run[-1]["candidate"]["tiles"])))
        if not sample["candidate"] or not adjacent:
            finish();run=[]
        if sample["candidate"]:run.append(sample)
    finish()
    first,last = (checked[0]["seconds"],checked[-1]["seconds"]) if checked else (0,0)
    gaps = any(b["seconds"]-a["seconds"] > SETTINGS["maximum_gap_seconds"] for a,b in zip(checked,checked[1:]))
    complete = len(checked)>=3 and last-first>=2 and not errors and not gaps
    return {"status": "checked" if complete else "not_assessed", "sample_count": len(checked),
            "invalid_samples": errors, "sample_gaps": gaps, "first_s": first, "last_s": last,
            "observed_seconds": last-first, "flagged_seconds": sum(r["end_s"]-r["start_s"] for r in runs), "runs": runs}
