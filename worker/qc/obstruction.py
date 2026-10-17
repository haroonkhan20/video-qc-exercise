"""Conservative, versioned screening of saved snapshots for dark edge blockage.

This is a review aid, not an object recognizer or a full-frame-video check.
"""
import hashlib
import io
from pathlib import Path

VERSION = "dark-edge-snapshots-v1"
from qc.rulebook import section
SETTINGS = section("obstruction")

def provenance(settings=None):
    settings=dict(SETTINGS if settings is None else settings)
    return {"version": VERSION, "source_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "settings": settings, "scope": "Saved snapshots, approximately one per second; not every frame. Dark edge blockages only."}

def inspect_image(data,settings=None):
    settings=dict(SETTINGS if settings is None else settings)
    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        gray = np.asarray(image.convert("L").resize((settings["image_size"], settings["image_size"])), dtype=float)
    grid=settings["grid"];tile_size=settings["image_size"]//grid
    dark = set()
    for y in range(grid):
        for x in range(grid):
            tile = gray[y*tile_size:(y+1)*tile_size, x*tile_size:(x+1)*tile_size]
            if (tile < settings["dark_pixel"]).mean() >= settings["dark_fraction"] and tile.std() <= settings["tile_std_max"]:
                dark.add((y, x))
    # Symmetric top/bottom or left/right bars are commonly normal letterboxing.
    if dark and (dark == {(y,x) for y in (0,grid-1) for x in range(grid)} or
                 dark == {(y,x) for x in (0,grid-1) for y in range(grid)}):
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
        area = len(component)/(grid*grid)
        if not settings["area_min"] <= area <= settings["area_max"]:continue
        if not any(y in (0,grid-1) or x in (0,grid-1) for y,x in component):continue
        mask = np.ones((settings["image_size"],settings["image_size"]),dtype=bool)
        for y,x in dark:mask[y*tile_size:(y+1)*tile_size,x*tile_size:(x+1)*tile_size] = False
        rest = gray[mask]
        if not len(rest) or rest.mean() < settings["remaining_mean_min"] or rest.std() < settings["remaining_std_min"]:continue
        return {"area_fraction": area, "tiles": sorted([list(p) for p in component])}
    return None

def summarize(samples,settings=None):
    """Samples are (relative seconds, JPEG bytes), with failures kept unknown."""
    settings=dict(SETTINGS if settings is None else settings)
    checked = [];errors = 0
    for seconds,data in sorted(samples):
        try:checked.append({"seconds": seconds, "candidate": inspect_image(data,settings)})
        except Exception:errors += 1
    runs = [];run = []
    def finish():
        if len(run) >= settings["minimum_samples"] and run[-1]["seconds"]-run[0]["seconds"] >= settings["minimum_seconds"]:
            runs.append({"start_s": run[0]["seconds"], "end_s": run[-1]["seconds"],
                         "samples": len(run), "maximum_area_fraction": max(s["candidate"]["area_fraction"] for s in run)})
    for sample in checked:
        adjacent = not run or (sample["seconds"]-run[-1]["seconds"] <= settings["maximum_gap_seconds"] and
                    set(map(tuple,sample["candidate"]["tiles"] if sample["candidate"] else [])) & set(map(tuple,run[-1]["candidate"]["tiles"])))
        if not sample["candidate"] or not adjacent:
            finish();run=[]
        if sample["candidate"]:run.append(sample)
    finish()
    first,last = (checked[0]["seconds"],checked[-1]["seconds"]) if checked else (0,0)
    gaps = any(b["seconds"]-a["seconds"] > settings["maximum_gap_seconds"] for a,b in zip(checked,checked[1:]))
    complete = len(checked)>=settings["completion_minimum_samples"] and last-first>=settings["completion_minimum_seconds"] and not errors and not gaps
    return {"status": "checked" if complete else "not_assessed", "sample_count": len(checked),
            "invalid_samples": errors, "sample_gaps": gaps, "first_s": first, "last_s": last,
            "observed_seconds": last-first, "flagged_seconds": sum(r["end_s"]-r["start_s"] for r in runs), "runs": runs}
