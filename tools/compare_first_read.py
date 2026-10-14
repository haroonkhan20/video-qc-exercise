#!/usr/bin/env python3
"""Compare frozen first-read guesses with full QC; this is not ground-truth accuracy."""
import csv,json,re
from pathlib import Path
def main():
    rows=[]
    for line in Path("DATA.md").read_text().splitlines():
        match=re.match(r"\| \[(ep_[0-9a-f]+\.mcap)\].*\| (Likely good \(initial sample\)|Likely bad|Uncertain: exposure context) \|",line)
        if not match:continue
        filename,guess=match.groups();report=json.loads((Path("reports")/(Path(filename).stem+".json")).read_text())
        label={"Likely good (initial sample)":"pass","Likely bad":"fail","Uncertain: exposure context":"needs_review"}[guess]
        actual=report["verdict"];codes=report["reason_codes"]
        explanation=""
        if label!=actual:
            if label=="needs_review" and actual=="pass":
                explanation="First-read exposure uncertainty did not violate the explicit sustained-extreme-image policy; visible contrast alone is not rejection."
            elif actual=="needs_review":
                explanation="Full checks found "+", ".join(codes)+"; the preliminary image sample did not comprehensively test this condition."
            else:
                explanation="Full-frame/timing checks found "+", ".join(codes)+" beyond the first-read sampling scope."
        rows.append({"file":filename,"digest":report["digest"],"initial_guess":guess,"initial_mapping":label,
                     "machine_verdict":actual,"reason_codes":codes,"agreement":label==actual,"disagreement_explanation":explanation})
    assert len(rows)==41
    table={a:{b:sum(r["initial_mapping"]==a and r["machine_verdict"]==b for r in rows) for b in ("pass","fail","needs_review")} for a in ("pass","fail","needs_review")}
    result={"basis":"Frozen Day 2 preliminary guesses, not independently established truth",
            "recordings":41,"agreement_count":sum(r["agreement"] for r in rows),"confusion_table":table,"cases":rows}
    Path("verification/first-read-comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    with Path("verification/reference-review.csv").open("w",newline="") as stream:
        columns=["file","digest","machine_verdict","reason_codes","reference_verdict","reviewer","reference_evidence","miss_explanation"]
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in rows:
            writer.writerow({"file":row["file"],"digest":row["digest"],"machine_verdict":row["machine_verdict"],"reason_codes":";".join(row["reason_codes"])})
    print(json.dumps({"recordings":41,"first_read_agreement":result["agreement_count"],"basis":result["basis"],"table":table},indent=2))
if __name__=="__main__":main()
