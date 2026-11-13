"""Create blank manual-audit sheets (coherence, metadata, grounding) from fixed, pre-declared samples.

Samples are fixed by rule, not by outcome:
  * coherence: the first 10 content pages in page order; position = the 60-char snippet at the
    middle of the page text; for each strategy A/B the first chunk containing it is shown.
  * metadata + grounding: the first 5 test questions in id order (T01-T05; includes two filter
    questions); top-3 of A, B, C taken from results/traces.jsonl.
Human columns are left EMPTY: labels must be given by the author. `auto_*` columns are only
mechanical hints (e.g. chunk text really occurs on the cited page) and do not replace the labels.

Usage (from starter/, after `python -m src.run`):  python scripts/make_audit_sheets.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.evaluation import squash  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402

OUT = ROOT / "results" / "audit"
N_COHERENCE, N_TEST_Q = 10, 5


def write(name: str, header: list[str], rows: list[list]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main() -> None:
    pages = load_corpus(ROOT / "data")
    traces = [json.loads(l) for l in (ROOT / "results" / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    page_text = {p.page: squash(p.text) for p in pages}
    chapter_of = {p.page: p.metadata["chapter"] for p in pages}

    # 1. coherence: same 10 positions for each strategy
    rows = []
    for p in sorted(pages, key=lambda p: p.page)[:N_COHERENCE]:
        flat = re.sub(r"\s+", " ", p.text)
        mid = max(0, len(flat) // 2 - 30)
        snippet = squash(flat[mid:mid + 60])
        for name, chunks in (("A", fixed_size(p, 500, 50)), ("B", by_paragraph(p, 800))):
            hit = next((c for c in chunks if snippet in squash(c.text)), None)
            if hit is None:  # snippet straddles a chunk border: fall back to the chunk with its first half
                hit = next(c for c in chunks if snippet[:25] in squash(c.text))
            rows.append([name, p.page, flat[mid:mid + 60], hit.chunk_id, len(hit.text), hit.text, "", ""])
    write("coherence_sheet.csv",
          ["strategy", "page", "position_snippet", "chunk_id", "chunk_len", "chunk_text",
           "score_0_1_2 (HUMAN)", "reason (HUMAN)"], rows)

    # 2. metadata + 3. grounding on the first 5 test questions
    test_ids = sorted({t["id"] for t in traces if t["split"] == "test"})[:N_TEST_Q]
    meta_rows, ground_rows = [], []
    for t in traces:
        if t["id"] not in test_ids:
            continue
        for rank, h in enumerate(t["top3"], 1):
            m = h["metadata"]
            meta_rows.append([t["strategy"], t["id"], rank, h["chunk_id"], m["document_id"], m["page"], m["chapter"],
                              json.dumps(t["filter"]) if t["filter"] else "",
                              squash(h["text"]) in page_text.get(m["page"], ""),
                              chapter_of.get(m["page"]) == m["chapter"],
                              (m["chapter"] == t["filter"]["chapter"]) if t["filter"] else "",
                              "", ""])
        shown = "\n\n".join(f"[#{i} trang {h['metadata']['page']}, ch.{h['metadata']['chapter']}] {h['text']}"
                            for i, h in enumerate(t["top3"], 1))
        ground_rows.append([t["strategy"], t["id"], t["question"], t["evidence_quote"], shown, "", ""])
    meta_rows.sort(key=lambda r: (r[1], r[0], r[2]))
    ground_rows.sort(key=lambda r: (r[1], r[0]))
    write("metadata_sheet.csv",
          ["strategy", "qid", "rank", "chunk_id", "source", "page", "chapter", "filter",
           "auto_text_on_cited_page", "auto_chapter_matches_page", "auto_filter_respected",
           "metadata_ok TRUE/FALSE (HUMAN)", "error_note (HUMAN)"], meta_rows)
    write("grounding_sheet.csv",
          ["strategy", "qid", "question", "gold_evidence", "top3", "score_0_1_2 (HUMAN)", "reason (HUMAN)"], ground_rows)


if __name__ == "__main__":
    main()
