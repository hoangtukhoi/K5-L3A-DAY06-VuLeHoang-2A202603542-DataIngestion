"""Read and normalize source data."""
import json
import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

log = logging.getLogger(__name__)
MIN_CHARS = 300  # same content-page rule as scripts/prepare_corpus.py


def normalize_text(text: str) -> str:
    """NFC-normalize, drop the page-number header line, collapse spaces; keep line breaks.

    Line breaks are kept because chunking.by_paragraph uses them to find structure.
    Known limit: stray spaces inside Vietnamese words from the PDF extractor are not repaired.
    """
    text = unicodedata.normalize("NFC", text or "").replace("\r", "")
    text = text.replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    if lines and re.fullmatch(r"\d{1,3}", lines[0]):  # running page number at top of page
        lines = lines[1:]
    return "\n".join(lines)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract every physical page (1-based page number); empty pages are logged, not hidden."""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = normalize_text(page.extract_text())
        except Exception as exc:  # record the failure and continue
            log.warning("%s page %d: extraction failed (%s)", document_id, i, exc)
            text = ""
        if not text:
            log.warning("%s page %d: no text extracted", document_id, i)
        pages.append(DocumentPage(document_id, source, i, text, {}))
    return pages


def load_corpus(data_dir: Path) -> list[DocumentPage]:
    """Load only the content pages listed in data/manifest.json, with chapter metadata."""
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for src in manifest["sources"]:
        by_page = {p["pdf_page"]: p for p in src["pages"]}
        pdf_path = data_dir / Path(src["source_path_or_url"].split(" ")[0]).name
        for page in load_pdf(pdf_path, src["source_id"], pdf_path.name):
            info = by_page.get(page.page)
            if info is None:
                continue
            if len(page.text) < MIN_CHARS:
                log.warning("%s page %d: listed as content but only %d chars", page.document_id, page.page, len(page.text))
            page.metadata = {"chapter": info["chapter"], "chapter_title": info["chapter_title"]}
            out.append(page)
    return out
