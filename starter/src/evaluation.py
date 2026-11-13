"""Evaluate retrieved evidence and preserve per-query traces.

Hit definition (GUIDE.md): a retrieved chunk is a hit when it comes from the gold source and
page AND contains the whole evidence_quote (Unicode NFC, whitespace ignored because the PDF
extractor inserts stray spaces). Extra, looser diagnostics are reported separately and never
replace the main metric. Coherence, metadata correctness and grounding need human labels;
nothing here infers them.
"""
import re
import unicodedata
from collections import defaultdict
from typing import Any


def squash(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


def _gold_pages(question: dict[str, Any]) -> set[int]:
    pages = question.get("alt_gold_pages") or []
    return {question["gold_page"], *pages}


def is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    meta = hit["metadata"]
    return (meta["document_id"] == question["gold_source_id"]
            and meta["page"] in _gold_pages(question)
            and squash(question["evidence_quote"]) in squash(hit["text"]))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    top = hits[:3]
    flags = [is_hit(question, h) for h in top]
    page_match = [h["metadata"]["document_id"] == question["gold_source_id"]
                  and h["metadata"]["page"] in _gold_pages(question) for h in top]
    first_hit = flags.index(True) + 1 if any(flags) else None
    return {
        "hit_at_1": bool(flags[:1] and flags[0]),
        "hit_at_3": any(flags),
        "first_hit_rank": first_hit,
        # diagnostics: right page retrieved but the quote is not whole inside any chunk of it
        "page_hit_at_3": any(page_match),
        "evidence_split_or_cut": any(page_match) and not any(flags),
        "filter_respected": (None if not question.get("filter") else
                             all(h["metadata"].get(k) == v for h in top for k, v in question["filter"].items())),
        "ranks_hit": flags,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate by strategy and split; always report numerator/denominator."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t)
        groups[(t["strategy"], "all")].append(t)
    out: dict[str, Any] = {}
    for (strategy, split), rows in sorted(groups.items()):
        n = len(rows)
        filt = [r for r in rows if r["filter"]]
        out.setdefault(strategy, {})[split] = {
            "n": n,
            "hit_at_1": f"{sum(r['eval']['hit_at_1'] for r in rows)}/{n}",
            "hit_at_3": f"{sum(r['eval']['hit_at_3'] for r in rows)}/{n}",
            "page_hit_at_3": f"{sum(r['eval']['page_hit_at_3'] for r in rows)}/{n}",
            "evidence_split_or_cut": sum(r["eval"]["evidence_split_or_cut"] for r in rows),
            "filter_questions": len(filt),
            "filter_respected": (f"{sum(bool(r['eval']['filter_respected']) for r in filt)}/{len(filt)}"
                                 if filt else "N/A"),
            "hit_at_3_on_filter_questions": (f"{sum(r['eval']['hit_at_3'] for r in filt)}/{len(filt)}" if filt else "N/A"),
        }
    return out
