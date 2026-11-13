"""Fixed-size and structure-aware chunking. Chunks never cross page boundaries."""
import re

from .models import Chunk, DocumentPage

HEADING = re.compile(r"^\d+\.\d+(\.\d+)*\.?\s+\S")      # "1.3. ..." / "2.4.1. Các cấu trúc rẽ nhánh"; not "3. Bài tập" items
BLOCK_START = re.compile(r"^(Hình|Bảng)\s+\d+|^[•\-–]\s|^\d+\.\s")  # captions, bullets, numbered items
SENTENCE_END = re.compile(r"[.:;?!)\]]$")


def _meta(page: DocumentPage, strategy: str) -> dict:
    return {**page.metadata, "strategy": strategy}


def _make(page: DocumentPage, strategy: str, idx: int, text: str) -> Chunk:
    return Chunk(f"{page.document_id}-p{page.page:03d}-{strategy}{idx:02d}",
                 page.document_id, page.source, page.page, text, _meta(page, strategy))


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Strategy A: overlapping character windows over the page text (newlines -> spaces)."""
    assert 0 <= overlap < size
    text = re.sub(r"\s+", " ", page.text).strip()
    step = size - overlap
    chunks = []
    for idx, start in enumerate(range(0, max(len(text), 1), step)):
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(_make(page, "A", idx, piece))
        if start + size >= len(text):
            break
    return chunks


def paragraphs(text: str) -> list[str]:
    """Rebuild paragraphs from hard-wrapped PDF lines.

    The extractor emits one '\\n' per visual line, so a new paragraph starts at a heading,
    caption, bullet or numbered item, or after a line that ends a sentence and is clearly
    shorter than a full-width line.
    """
    lines = text.split("\n")
    full = sorted(len(l) for l in lines)[int(len(lines) * 0.8)] if lines else 0  # typical full-line width
    paras, cur = [], []
    for line in lines:
        starts_block = bool(HEADING.match(line) and len(line) < 90) or bool(BLOCK_START.match(line))
        prev_ends = bool(cur) and SENTENCE_END.search(cur[-1]) and len(cur[-1]) < 0.8 * full
        if cur and (starts_block or prev_ends):
            paras.append(" ".join(cur))
            cur = []
        cur.append(line)
        if HEADING.match(line) and len(line) < 90:  # keep a heading as its own block start
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return [p for p in paras if p.strip()]


def _split_oversized(par: str, max_size: int) -> list[str]:
    """Split a paragraph longer than max_size at sentence boundaries, then by words."""
    if len(par) <= max_size:
        return [par]
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", par):
        while len(sent) > max_size:  # a single very long sentence: cut at a space
            cut = sent.rfind(" ", 0, max_size)
            cut = cut if cut > 0 else max_size
            if cur: parts.append(cur); cur = ""
            parts.append(sent[:cut]); sent = sent[cut:].strip()
        if cur and len(cur) + 1 + len(sent) > max_size:
            parts.append(cur); cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return parts


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Strategy B: pack whole paragraphs up to max_size; a heading starts a new chunk; split oversized ones at sentences."""
    units = [u for p in paragraphs(page.text) for u in _split_oversized(p, max_size)]
    chunks, cur = [], ""
    for u in units:
        is_heading = bool(HEADING.match(u)) and len(u) < 90
        if cur and (is_heading or len(cur) + 1 + len(u) > max_size):  # a heading always opens a new chunk
            chunks.append(_make(page, "B", len(chunks), cur)); cur = u
        else:
            cur = f"{cur} {u}".strip()
    if cur:
        chunks.append(_make(page, "B", len(chunks), cur))
    return chunks
