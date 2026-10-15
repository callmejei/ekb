"""Structure-aware chunking: split by heading, 400–800 tokens with ~15% overlap, tables kept whole,
each chunk prefixed with its heading path."""

from dataclasses import dataclass

from .extract import Element

MAX_TOKENS = 800
TARGET_TOKENS = 600
OVERLAP_RATIO = 0.15


def n_tokens(text: str) -> int:
    # Close enough for sizing without loading a tokenizer: ~1.3 tokens per English word.
    return int(len(text.split()) * 1.3) + 1


@dataclass
class Chunk:
    seq: int
    page: int
    heading_path: str
    text: str  # body without the heading prefix
    chunk_type: str  # text | table

    @property
    def indexed_text(self) -> str:
        return f"{self.heading_path}\n\n{self.text}" if self.heading_path else self.text


def _split_long(text: str, max_tokens: int) -> list[str]:
    words = text.split()
    step = int(max_tokens / 1.3)
    return [" ".join(words[i : i + step]) for i in range(0, len(words), step)]


def chunk_elements(elements: list[Element], title: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    buf: list[tuple[int, str]] = []  # (page, paragraph)

    def path() -> str:
        return " > ".join([title, *[h for _, h in stack]])

    def emit(page: int, text: str, kind: str) -> None:
        chunks.append(Chunk(len(chunks), page, path(), text, kind))

    def flush() -> None:
        nonlocal buf
        paras: list[tuple[int, str]] = []
        for page, p in buf:
            if n_tokens(p) > MAX_TOKENS:
                paras.extend((page, part) for part in _split_long(p, TARGET_TOKENS))
            else:
                paras.append((page, p))
        current: list[tuple[int, str]] = []
        for para in paras:
            if current and n_tokens(" ".join(p for _, p in current + [para])) > MAX_TOKENS:
                emit(current[0][0], "\n\n".join(p for _, p in current), "text")
                # carry the tail forward as overlap (~15% of target)
                overlap: list[tuple[int, str]] = []
                for prev in reversed(current):
                    if n_tokens(" ".join(p for _, p in overlap + [prev])) > TARGET_TOKENS * OVERLAP_RATIO:
                        break
                    overlap.insert(0, prev)
                current = overlap
            current.append(para)
        if current:
            emit(current[0][0], "\n\n".join(p for _, p in current), "text")
        buf = []

    for e in elements:
        if e.kind == "heading":
            flush()
            while stack and stack[-1][0] >= e.level:
                stack.pop()
            stack.append((e.level, e.text))
        elif e.kind == "table" and e.table:
            flush()
            caption = e.table.get("caption") or ""
            body = (f"Table: {caption}\n\n" if caption else "") + e.table["markdown"]
            emit(e.page, body, "table")  # never split a table
        elif e.text.strip():
            buf.append((e.page, e.text))
    flush()
    return chunks
