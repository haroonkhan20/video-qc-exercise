"""Grade exported evidence offline; never reads raw files or changes verdicts."""
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
from grading import validate_profile
from server import graded

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=ROOT / "web/grading_profiles/balanced-v1.json")
    parser.add_argument("--output", type=Path, default=ROOT / "verification/grading.json")
    args = parser.parse_args()
    profile = validate_profile(json.loads(args.profile.read_text()))
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Output must stay under this repository")
    rows = []
    for path in sorted((ROOT / "reports").glob("ep_*.json")):
        report = json.loads(path.read_text())
        result = graded(report, profile)
        rows.append({"file": path.stem + ".mcap", **{k: result[k] for k in (
            "digest", "original_verdict", "score", "weighted_average", "recommendation",
            "assessment_complete", "possible_range", "critical_cap", "why", "source_report_hash")},
            "scorecard": result["scorecard"],
            "legacy_category_grade": result["legacy_category_grade"]})
    if not rows:
        parser.error("No exported episode reports found")
    evidence = {"engine_version": result["engine_version"], "engine_hash": result["engine_hash"],
                "profile": profile, "profile_version": result["profile_version"],
                "scope": "Regrading exported measurements; does not rerun decoding or replace original verdicts",
                "count": len(rows), "recommendations": dict(Counter(r["recommendation"] for r in rows)), "recordings": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "count": len(rows), "recommendations": evidence["recommendations"]}))

if __name__ == "__main__":main()
