"""Collection membership uses known fingerprints, never diagnostic filenames."""
import json,re
def known_tests(path):
    if not path.exists():return set()
    data=json.loads(path.read_text())
    values={r["digest"] for r in data["recordings"]}
    if any(not isinstance(v,str) or not re.fullmatch("[0-9a-f]{64}",v) for v in values):
        raise ValueError("Invalid test-recording fingerprint registry")
    return values

def classify(digest,originals,tests):
    if digest in originals:return "reference"
    return "test" if digest in tests else "upload"
