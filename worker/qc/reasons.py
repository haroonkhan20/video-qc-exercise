"""One authoritative reason-code registry; no verdict policy is changed here."""
import json,re
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]/"config/reason-codes.json"
def load_registry(path=SOURCE):
 data=json.loads(Path(path).read_text())
 if set(data)!={"schema_version","codes"} or data["schema_version"]!=1 or not isinstance(data["codes"],dict):
  raise ValueError("Invalid reason registry")
 for code,item in data["codes"].items():
  if not re.fullmatch(r"[A-Z][A-Z0-9_]*",code) or set(item)!={"groups","description","kind"}:
   raise ValueError("Invalid reason definition")
  if not isinstance(item["groups"],list) or not all(isinstance(g,str) for g in item["groups"]) or item["kind"] not in {"success","finding","score_only"} or not isinstance(item["description"],str):
   raise ValueError("Invalid reason fields")
 return data["codes"]
REGISTRY=load_registry()
CODES=frozenset(REGISTRY)
PIPELINE_CODES=frozenset(k for k,v in REGISTRY.items() if v["kind"]!="score_only")
def group(name):return frozenset(k for k,v in REGISTRY.items() if name in v["groups"])
def constraint_sql():
 # SQL identifiers are fixed; registry identifiers are validated above.
 allowed="ARRAY["+ ",".join("'"+code+"'" for code in sorted(PIPELINE_CODES))+"]::text[]"
 return """DO $registry$
 DECLARE allowed text[] := """+allowed+""";
 BEGIN
  IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='qc_run_reason_codes') THEN
   ALTER TABLE qc_runs DROP CONSTRAINT qc_run_reason_codes;
  END IF;
  ALTER TABLE qc_runs ADD CONSTRAINT qc_run_reason_codes CHECK(reason_codes <@ allowed_reason_codes_placeholder);
  IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='qc_verdict_reason_codes') THEN
   ALTER TABLE qc_verdicts DROP CONSTRAINT qc_verdict_reason_codes;
  END IF;
  ALTER TABLE qc_verdicts ADD CONSTRAINT qc_verdict_reason_codes CHECK(reason_codes <@ allowed_reason_codes_placeholder);
 END $registry$;""".replace("allowed_reason_codes_placeholder",allowed)
