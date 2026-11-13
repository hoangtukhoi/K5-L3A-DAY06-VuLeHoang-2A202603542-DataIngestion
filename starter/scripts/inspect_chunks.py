"""Chunk the corpus with strategy A and B, print statistics and write samples.

Usage (from starter/):  python scripts/inspect_chunks.py
Writes results/chunk_stats.json and results/chunk_samples.txt.
"""
import json
import logging
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402

A_SIZE, A_OVERLAP, B_MAX = 500, 50, 800
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    t0 = time.perf_counter()
    pages = load_corpus(ROOT / "data")
    t_load = time.perf_counter() - t0
    stats, samples = {"pages": len(pages), "load_seconds": round(t_load, 2)}, []
    for name, fn in [("A", lambda p: fixed_size(p, A_SIZE, A_OVERLAP)), ("B", lambda p: by_paragraph(p, B_MAX))]:
        t0 = time.perf_counter()
        chunks = [c for p in pages for c in fn(p)]
        dt = time.perf_counter() - t0
        lens = [len(c.text) for c in chunks]
        stats[name] = {"chunks": len(chunks), "total_chars": sum(lens), "mean": round(statistics.mean(lens)),
                       "median": statistics.median(lens), "min": min(lens), "max": max(lens),
                       "under_100": sum(l < 100 for l in lens), "seconds": round(dt, 3)}
        for c in chunks:
            if c.page in (31, 117, 154):
                samples.append(f"=== {c.chunk_id} ch{c.metadata['chapter']} len={len(c.text)}\n{c.text}\n")
    print(json.dumps(stats, indent=2))
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    (out / "chunk_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (out / "chunk_samples.txt").write_text("\n".join(samples), encoding="utf-8")


if __name__ == "__main__":
    main()
