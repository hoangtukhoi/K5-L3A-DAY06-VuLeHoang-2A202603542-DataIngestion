"""Summarize the HUMAN labels in results/audit/*.csv. Refuses to run on empty labels.

Usage (from starter/):  python scripts/summarize_audit.py
Writes results/audit/audit_summary.json.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "results" / "audit"


def rows(name):
    with open(AUDIT / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def score_sheet(name, key):
    by = defaultdict(list)
    for r in rows(name):
        v = r[key].strip()
        if v not in {"0", "1", "2"}:
            sys.exit(f"{name}: unlabeled or invalid score ({v!r}) for {r['strategy']} / {r.get('qid') or r.get('page')}")
        by[r["strategy"]].append(int(v))
    return {s: {"n": len(v), "counts": dict(sorted(Counter(v).items())), "mean_of_2": round(sum(v) / len(v), 2)}
            for s, v in sorted(by.items())}


def main() -> None:
    out = {"coherence": score_sheet("coherence_sheet.csv", "score_0_1_2 (HUMAN)"),
           "grounding": score_sheet("grounding_sheet.csv", "score_0_1_2 (HUMAN)")}
    meta = defaultdict(lambda: [0, 0])
    for r in rows("metadata_sheet.csv"):
        v = r["metadata_ok TRUE/FALSE (HUMAN)"].strip().upper()
        if v not in {"TRUE", "FALSE"}:
            sys.exit(f"metadata_sheet.csv: unlabeled row {r['strategy']} {r['qid']} #{r['rank']}")
        meta[r["strategy"]][0] += v == "TRUE"; meta[r["strategy"]][1] += 1
    out["metadata_ok"] = {s: f"{a}/{b}" for s, (a, b) in sorted(meta.items())}
    flt = defaultdict(lambda: [0, 0])  # per question: filter respected by all top-3
    per_q = defaultdict(list)
    for r in rows("metadata_sheet.csv"):
        if r["filter"]:
            per_q[(r["strategy"], r["qid"])].append(r["auto_filter_respected"] == "True")
    for (s, _), v in per_q.items():
        flt[s][0] += all(v); flt[s][1] += 1
    out["filter_questions_respected (auto)"] = {s: f"{a}/{b}" for s, (a, b) in sorted(flt.items())}
    (AUDIT / "audit_summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
