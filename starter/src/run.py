"""Run the benchmark for strategies A, B and C and save full top-3 traces.

A: fixed-size chunks (500/50), no filter.   B: paragraph chunks (<=800), no filter.
C: the same B index, but questions that carry a `filter` are queried with it (others: no filter).

Selection criterion (fixed before looking at test): highest Evidence Hit@3 on DEV, ties broken
by Hit@1 on dev, then fewer chunks. Test numbers are reported only after the choice is made.

Usage (from starter/):  python -m src.run
"""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT.parent / "benchmark" / "questions.jsonl"
RESULTS = ROOT / "results"
# strategy -> (index stored under, whether question filters are applied)
STRATEGIES = {"A": ("A", False), "B": ("B", False), "C": ("B", True)}


def main() -> None:
    load_dotenv(ROOT / ".env")
    questions = [json.loads(l) for l in BENCH.read_text(encoding="utf-8").splitlines() if l.strip()]
    emb = MyEmbedder()
    store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
    for index in ("A", "B"):
        if store.count(index) == 0:
            raise SystemExit(f"index {index} is empty: run `python scripts/ingest.py` first")
    t0 = time.perf_counter()
    qvecs = {q["id"]: emb.embed_query(q["question"]) for q in questions}
    t_embed = time.perf_counter() - t0

    traces, timing = [], {}
    for name, (index, use_filter) in STRATEGIES.items():
        t0 = time.perf_counter()
        for q in questions:
            flt = q["filter"] if (use_filter and q["filter"]) else None
            hits = store.search(index, qvecs[q["id"]], 3, flt)
            traces.append({"strategy": name, "id": q["id"], "split": q["split"], "type": q["type"],
                           "question": q["question"], "filter": q["filter"], "filter_applied": flt,
                           "gold_page": q["gold_page"], "evidence_quote": q["evidence_quote"],
                           "top3": hits, "eval": evaluate_query(q, hits)})
        timing[name] = round(time.perf_counter() - t0, 3)

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "traces.jsonl", "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    metrics = {"model": emb.model_name, "n_questions": len(questions),
               "query_embedding_seconds": round(t_embed, 2), "search_seconds": timing,
               "metrics": summarize(traces)}
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    print("DEV (used to choose the configuration)")
    for s, d in metrics["metrics"].items():
        print(f"  {s}: Hit@1 {d['dev']['hit_at_1']}  Hit@3 {d['dev']['hit_at_3']}  page@3 {d['dev']['page_hit_at_3']}")
    print("TEST (report only, do not tune on it)")
    for s, d in metrics["metrics"].items():
        print(f"  {s}: Hit@1 {d['test']['hit_at_1']}  Hit@3 {d['test']['hit_at_3']}  page@3 {d['test']['page_hit_at_3']}")


if __name__ == "__main__":
    main()
