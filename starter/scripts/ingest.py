"""Ingest strategies A and B into pgvector; run twice to prove re-ingestion adds no duplicates.

Strategy C has no rows of its own: it queries B's rows with a metadata filter.
Usage (from starter/):  python scripts/ingest.py
Writes results/ingest_stats.json.
"""
import json
import logging
import os
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.embeddings import MyEmbedder  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402
from src.store import PgVectorStore  # noqa: E402

A_SIZE, A_OVERLAP, B_MAX = 500, 50, 800


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    load_dotenv(ROOT / ".env")
    pages = load_corpus(ROOT / "data")
    t0 = time.perf_counter()
    emb = MyEmbedder()
    t_model = time.perf_counter() - t0
    store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
    store.create_schema()
    strategies = {
        "A": [c for p in pages for c in fixed_size(p, A_SIZE, A_OVERLAP)],
        "B": [c for p in pages for c in by_paragraph(p, B_MAX)],
    }
    stats = {"model": emb.model_name, "dimensions": emb.dimensions, "cost_usd": 0.0,
             "versions": {k: version(k) for k in ("sentence-transformers", "torch", "psycopg", "pypdf")},
             "python": platform.python_version(), "vector_store": "PostgreSQL 16 + pgvector 0.8.7 (exact cosine, no ANN index)",
             "model_load_seconds": round(t_model, 2), "params": {"A": {"size": A_SIZE, "overlap": A_OVERLAP}, "B": {"max_size": B_MAX}},
             "strategies": {}}
    for name, chunks in strategies.items():
        run = {}
        for attempt in ("first_ingest", "reingest_same_data"):
            t0 = time.perf_counter()
            vectors = emb.embed_documents([c.text for c in chunks])
            t_embed = time.perf_counter() - t0
            res = store.upsert(name, chunks, vectors)
            run[attempt] = {**res, "embed_seconds": round(t_embed, 2),
                            "total_seconds": round(time.perf_counter() - t0, 2)}
            print(name, attempt, run[attempt])
        # simulate a changed corpus: drop the last 5 chunks and check obsolete rows are removed, then restore
        kept = chunks[:-5]
        run["changed_corpus_check"] = store.upsert(name, kept, emb.embed_documents([c.text for c in kept]))
        run["restore"] = store.upsert(name, chunks, emb.embed_documents([c.text for c in chunks]))
        run["chunks"] = len(chunks)
        stats["strategies"][name] = run
        print(name, "changed corpus:", run["changed_corpus_check"], "| restored:", run["restore"])
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    (out / "ingest_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
