"""PDF → structured elements (headings, paragraphs, tables) with page numbers, plus Markdown.

Default extractor is PyMuPDF (fast, no model downloads). EXTRACTOR=docling switches to Docling
when it is installed; both produce the same element structure so downstream stages don't care.
"""

import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import fitz  # PyMuPDF


@dataclass
class Element:
    page: int
    kind: str  # heading | text | table
    text: str
    level: int = 0
    table: dict[str, Any] | None = None


@dataclass
class Extraction:
    elements: list[Element] = field(default_factory=list)
    page_count: int = 0

    @property
    def tables(self) -> list[dict[str, Any]]:
        return [dict(e.table, page=e.page) for e in self.elements if e.kind == "table" and e.table]

    def to_markdown(self) -> str:
        out: list[str] = []
        current_page = 0
        for e in self.elements:
            if e.page != current_page:
                current_page = e.page
                out.append(f"\n<!-- page {current_page} -->\n")
            if e.kind == "heading":
                out.append(f"{'#' * max(1, e.level)} {e.text}\n")
            elif e.kind == "table" and e.table:
                out.append(e.table["markdown"] + "\n")
            else:
                out.append(e.text + "\n")
        return "\n".join(out)


def _clean(s: str | None) -> str:
    # NFKC folds typographic ligatures (ﬁ, ﬀ, ﬂ) back to plain letters so keyword search matches.
    return " ".join(unicodedata.normalize("NFKC", s or "").split())


def _table_markdown(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _inside(bbox: tuple[float, float, float, float], boxes: list[fitz.Rect]) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return any(r.contains(fitz.Point(cx, cy)) for r in boxes)


def extract_pymupdf(data: bytes) -> Extraction:
    doc = fitz.open(stream=data, filetype="pdf")
    # Body font size = the size carrying the most characters across the document.
    sizes: Counter[float] = Counter()
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for span in line["spans"]:
                    sizes[round(span["size"], 1)] += len(span["text"].strip())
    body = sizes.most_common(1)[0][0] if sizes else 10.0
    heading_sizes = sorted({s for s in sizes if s >= body + 1.5}, reverse=True)

    def heading_level(size: float) -> int:
        return heading_sizes.index(size) + 1 if size in heading_sizes else 0

    result = Extraction(page_count=doc.page_count)
    for pno, page in enumerate(doc, start=1):
        items: list[tuple[float, Element]] = []
        table_boxes: list[fitz.Rect] = []
        try:
            tables = page.find_tables().tables
        except Exception:
            tables = []
        for t in tables:
            raw = t.extract()
            if not raw or len(raw) < 2:
                continue
            header = [_clean(c) for c in raw[0]]
            rows = [[_clean(c) for c in r] for r in raw[1:] if any(_clean(c) for c in r)]
            table_boxes.append(fitz.Rect(t.bbox))
            items.append(
                (
                    t.bbox[1],
                    Element(
                        pno,
                        "table",
                        _table_markdown(header, rows),
                        table={"header": header, "rows": rows, "markdown": _table_markdown(header, rows), "caption": ""},
                    ),
                )
            )

        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0 or _inside(b["bbox"], table_boxes):
                continue
            # Drop running headers/footers (page numbers, disclaimers) in the top and bottom bands.
            if b["bbox"][1] > page.rect.height - 50 or b["bbox"][3] < 40:
                continue
            spans = [s for line in b["lines"] for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = _clean(" ".join(" ".join(s["text"] for s in line["spans"]) for line in b["lines"]))
            size = round(max(s["size"] for s in spans), 1)
            level = heading_level(size)
            if level and len(text) < 120:
                items.append((b["bbox"][1], Element(pno, "heading", text, level=level)))
            else:
                items.append((b["bbox"][1], Element(pno, "text", text)))

        items.sort(key=lambda x: x[0])
        page_elements = [e for _, e in items]
        # Caption = nearest preceding heading/short line on the same page.
        for i, e in enumerate(page_elements):
            if e.kind == "table" and e.table is not None:
                for prev in reversed(page_elements[:i]):
                    if prev.kind in ("heading", "text") and len(prev.text) < 120:
                        e.table["caption"] = prev.text
                        break
        result.elements.extend(page_elements)

    _merge_continued_tables(result.elements)
    # Text without a text layer → OCR would go here (PaddleOCR, optional, not in the demo build).
    return result


def _merge_continued_tables(elements: list[Element]) -> None:
    """A table that runs over a page break comes back as two tables, the second one headed by
    what is really a data row. Re-join them so a table is never split."""
    i = 1
    while i < len(elements):
        prev, cur = elements[i - 1], elements[i]
        if (
            prev.kind == "table"
            and cur.kind == "table"
            and prev.table
            and cur.table
            and cur.page == prev.page + 1
            and not cur.table["caption"]
            and len(cur.table["header"]) == len(prev.table["header"])
        ):
            prev.table["rows"] += [cur.table["header"], *cur.table["rows"]]
            prev.table["markdown"] = _table_markdown(prev.table["header"], prev.table["rows"])
            prev.text = prev.table["markdown"]
            del elements[i]
            continue
        i += 1


def extract_docling(data: bytes) -> Extraction:  # pragma: no cover - optional dependency
    import tempfile

    from docling.document_converter import DocumentConverter

    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        doc = DocumentConverter().convert(f.name).document
    result = Extraction(page_count=len(doc.pages))
    for item, level in doc.iterate_items():
        page = item.prov[0].page_no if getattr(item, "prov", None) else 1
        label = str(getattr(item, "label", ""))
        if "table" in label:
            df = item.export_to_dataframe()
            header = [str(c) for c in df.columns]
            rows = [[str(v) for v in r] for r in df.values.tolist()]
            md = _table_markdown(header, rows)
            result.elements.append(
                Element(page, "table", md, table={"header": header, "rows": rows, "markdown": md, "caption": ""})
            )
        elif "header" in label or "title" in label:
            result.elements.append(Element(page, "heading", _clean(item.text), level=max(1, level)))
        elif getattr(item, "text", None):
            result.elements.append(Element(page, "text", _clean(item.text)))
    return result


def extract(data: bytes, extractor: str = "pymupdf") -> Extraction:
    if extractor == "docling":
        return extract_docling(data)
    return extract_pymupdf(data)


def probe_text(data: bytes, max_chars: int = 4000) -> str:
    """Cheap text sample used for the near-duplicate check at upload time."""
    doc = fitz.open(stream=data, filetype="pdf")
    parts: list[str] = []
    for page in doc:
        parts.append(page.get_text())
        if sum(len(p) for p in parts) > max_chars:
            break
    return _clean(" ".join(parts))[:max_chars]


def full_text(data: bytes) -> str:
    return _clean(" ".join(page.get_text() for page in fitz.open(stream=data, filetype="pdf")))
