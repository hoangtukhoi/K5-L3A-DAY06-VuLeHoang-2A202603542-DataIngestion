"""Verify benchmark/questions.jsonl against data/root_data.pdf.

Checks per question: required fields, unique id, split counts, filter count,
gold_page is a content page in data/manifest.json, filter chapter matches the
gold page's chapter, and evidence_quote occurs on gold_page (Unicode NFC,
whitespace ignored because PDF extraction inserts stray spaces).

Usage (from starter/):  python scripts/verify_benchmark.py
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["id", "split", "type", "question", "expected_answer",
            "gold_source_id", "gold_page", "evidence_quote", "filter"]


def squash(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


def main() -> int:
    qs = [json.loads(l) for l in (ROOT / "benchmark" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    manifest = json.loads((ROOT / "starter" / "data" / "manifest.json").read_text(encoding="utf-8"))
    pages = {p["pdf_page"]: p for p in manifest["sources"][0]["pages"]}
    reader = PdfReader(str(ROOT / "starter" / "data" / "root_data.pdf"))
    errors, seen = [], set()
    for q in qs:
        qid = q.get("id")
        missing = [k for k in REQUIRED if k not in q]
        if missing:
            errors.append(f"{qid}: missing fields {missing}"); continue
        if qid in seen: errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        pg = q["gold_page"]
        if pg not in pages:
            errors.append(f"{qid}: gold_page {pg} is not a content page"); continue
        if q["filter"] and q["filter"].get("chapter") != pages[pg]["chapter"]:
            errors.append(f"{qid}: filter {q['filter']} != chapter of page {pg} ({pages[pg]['chapter']})")
        if squash(q["evidence_quote"]) not in squash(reader.pages[pg - 1].extract_text()):
            errors.append(f"{qid}: evidence NOT found on page {pg}")
    n = len(qs)
    dev = sum(q["split"] == "dev" for q in qs); test = sum(q["split"] == "test" for q in qs)
    f_all = sum(bool(q["filter"]) for q in qs); f_test = sum(bool(q["filter"]) and q["split"] == "test" for q in qs)
    print(f"questions={n} dev={dev} test={test} filter={f_all} (test filter={f_test})")
    if n < 20 or dev < 15 or test < 5 or f_all < 3 or f_test < 1:
        errors.append("benchmark does not meet minimum counts (20 / 15 dev / 5 test / 3 filter / 1 test filter)")
    for e in errors: print("ERROR:", e)
    print("OK: all evidence verified" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
