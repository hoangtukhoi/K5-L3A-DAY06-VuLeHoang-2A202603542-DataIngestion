"""Build the manifest for the Day 06 corpus: data/root_data.pdf (Vietnamese Java OOP textbook).

Usage (from starter/):  python scripts/prepare_corpus.py

Page rule: pdf_page = 1-based page index of root_data.pdf (equals the printed page number).
A page counts as content if it lies in chapters 1-13 (pdf pages 7-232) and has >= 300
characters after Unicode NFC normalization. Table of contents, preface, appendices and
references are excluded. Chapter boundaries come from the book's own table of contents.
Writes data/manifest.json.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from pypdf import PdfReader

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCE = DATA / "root_data.pdf"
MIN_CHARS = 300

# (chapter number, title, first pdf page) from the printed table of contents.
CHAPTERS = [
    (1, "Mở đầu", 7), (2, "Ngôn ngữ lập trình Java", 20), (3, "Lớp và đối tượng", 48),
    (4, "Biến và các kiểu dữ liệu", 57), (5, "Hành vi của đối tượng", 70),
    (6, "Sử dụng thư viện Java", 85), (7, "Thừa kế và đa hình", 103),
    (8, "Lớp trừu tượng và interface", 124), (9, "Vòng đời của đối tượng", 143),
    (10, "Thành viên lớp và thành viên thực thể", 164), (11, "Ngoại lệ", 174),
    (12, "Chuỗi hóa đối tượng và vào ra file", 196),
    (13, "Lập trình tổng quát và các lớp Collection", 215),
]
LAST_CONTENT_PAGE = 232  # appendix A starts at 233


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"[ \t]+", " ", text).strip()


def chapter_of(page: int):
    cur = None
    for num, title, first in CHAPTERS:
        if page >= first:
            cur = (num, title)
    return cur


def main() -> None:
    reader = PdfReader(str(SOURCE))
    pages, excluded = [], []
    for p in range(1, len(reader.pages) + 1):
        text = norm(reader.pages[p - 1].extract_text())
        if p < CHAPTERS[0][2] or p > LAST_CONTENT_PAGE:
            excluded.append({"pdf_page": p, "reason": "front matter / appendix / references"})
        elif len(text) < MIN_CHARS:
            excluded.append({"pdf_page": p, "reason": f"too short ({len(text)} chars)"})
        else:
            num, title = chapter_of(p)
            pages.append({"page_id": f"root_data-p{p:03d}", "pdf_page": p, "chapter": num,
                          "chapter_title": title, "chars": len(text)})
    manifest = {
        "page_counting_rule": __doc__.split("Page rule:")[1].split("Writes")[0].strip(),
        "filter_fields": {"chapter": "int 1-13, from the book's table of contents"},
        "known_issues": "Text extraction splits some Vietnamese words with stray spaces "
                        "(e.g. 'Ch ươ ng'); only NFC + whitespace collapsing is applied.",
        "total_content_pages": len(pages),
        "sources": [{
            "source_id": "root_data",
            "title": "Giáo trình Lập trình hướng đối tượng (OOP_2013) - VNU-UET, Trần Thị Minh Châu (thông tin do học viên khai, chưa kiểm chứng từ nguồn)",
            "source_path_or_url": "starter/data/root_data.pdf - tài liệu do giảng viên môn học cung cấp cho sinh viên (học viên khai)",
            "license_or_permission": "Giảng viên cung cấp cho sinh viên để học tập; chỉ dùng nội bộ cho lab, không phân phối lại, PDF không commit. Cần xác nhận bằng văn bản/tin nhắn của giảng viên nếu có.",
            "accessed_at": date.today().isoformat(),
            "physical_pages": len(reader.pages),
            "pdf_metadata": {k: str(v) for k, v in (reader.metadata or {}).items()},
            "pages": pages,
            "total_chars": sum(x["chars"] for x in pages),
            "excluded_pages": excluded,
        }],
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("content pages:", len(pages), "| excluded:", len(excluded), "| chars:", manifest["sources"][0]["total_chars"])
    for r in excluded:
        if "short" in r["reason"]:
            print("  short:", r)


if __name__ == "__main__":
    main()
