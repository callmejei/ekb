"""Grounded answer generation with citations to document, version and page."""

import re

from .. import llm

SYSTEM = """You are the bank's enterprise knowledge assistant.
Answer ONLY from the numbered sources provided. Do not use outside knowledge.
If the sources do not contain the answer, reply exactly: "I could not find this in the documents you have access to."
Cite every factual statement with the source number in square brackets, e.g. [1] or [2][3].
Be concise and precise: quote figures, rates and conditions exactly as written.
Use short paragraphs or bullet points; at most 7 bullets and 150 words.
"Knowledge graph facts" are verified links between documents (which policy governs which product,
which regulation requires which policy); use them, with their source number, when relevant."""

NOT_FOUND = "I could not find this in the documents you have access to."


def tables_as_records(text: str) -> str:
    """Markdown tables → one labelled record per row ("Loan amount: …; Approval authority: …").
    Small models misread row/column alignment in pipe tables; labelled records they read reliably."""
    out: list[str] = []
    header: list[str] | None = None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if header is None:
                header = cells
            elif all(set(c) <= set("-: ") for c in cells):
                continue
            else:
                out.append("- " + "; ".join(f"{h}: {v}" for h, v in zip(header, cells)))
        else:
            header = None
            out.append(line)
    return "\n".join(out)


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] {c['title']} (version {c.get('version_no', '?')}, page {c['page']})\n"
            f"Section: {c['heading_path']}\n{tables_as_records(c['chunk_text'])}"
        )
    return "\n\n---\n\n".join(parts)


def graph_facts(chunks: list[dict], relations: list[dict]) -> str:
    index = {c["chunk_id"]: i for i, c in enumerate(chunks, start=1)}
    lines = []
    for r in relations:
        n = index.get(r.get("evidence") or "")
        if n:
            lines.append(f"- {r['source']} {r['rel']} {r['target']} [{n}]")
    return ("Knowledge graph facts:\n" + "\n".join(lines) + "\n\n") if lines else ""


def generate(
    question: str,
    chunks: list[dict],
    *,
    actor: str,
    trace_id: str,
    relations: list[dict] | None = None,
    data_block: str | None = None,
) -> tuple[str, list[dict]]:
    if not chunks and not data_block:
        return NOT_FOUND, []
    facts = graph_facts(chunks, relations or [])
    data_part = f"Data query result (structured data, cite it as [SQL]):\n{data_block}\n\n" if data_block else ""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Sources:\n\n{build_context(chunks)}\n\n{facts}{data_part}Question: {question}"},
    ]
    text = llm.chat(messages, actor=actor, purpose=f"answer:{trace_id}", max_tokens=450).strip()

    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(chunks)})
    # Renumber citations 1..n in order of first use so the UI shows a clean list.
    order: list[int] = []
    for n in re.findall(r"\[(\d+)\]", text):
        n = int(n)
        if n in used and n not in order:
            order.append(n)
    mapping = {old: new for new, old in enumerate(order, start=1)}
    text = re.sub(r"\[(\d+)\]", lambda m: f"[{mapping[int(m.group(1))]}]" if int(m.group(1)) in mapping else "", text)

    citations = []
    for old in order:
        c = chunks[old - 1]
        citations.append(
            {
                "n": mapping[old],
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "version_id": c["version_id"],
                "version_no": c.get("version_no"),
                "title": c["title"],
                "page": c["page"],
                "heading_path": c["heading_path"],
                "snippet": c["chunk_text"][:400],
                "origin": c.get("origin", "hybrid"),
                "via": c.get("via", []),
            }
        )
    return text, citations
