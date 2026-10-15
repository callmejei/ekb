"""LLM enrichment: summary, key info, sample Q&A, entities and entity relations — validated
against a Pydantic schema, retried once on invalid output."""

import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .. import llm

log = logging.getLogger("ekb.enrich")

EntityType = Literal["Product", "Policy", "Regulation", "BusinessUnit"]


class Entity(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: EntityType


class Relation(BaseModel):
    source: str
    type: Literal["GOVERNS", "REQUIRES"]
    target: str


class QA(BaseModel):
    question: str
    answer: str


class Enrichment(BaseModel):
    summary: str = Field(min_length=20)
    key_info: dict[str, str] = Field(default_factory=dict)
    sample_qa: list[QA] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)

    @field_validator("key_info", mode="before")
    @classmethod
    def _stringify(cls, v: object) -> object:
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        return v


PROMPT = """You are cataloguing a bank document for an enterprise knowledge base.
Read the document and return ONLY a JSON object with exactly these keys:

"summary": 3-4 sentence plain-English summary.
"key_info": object of up to 8 short fields, e.g. {{"interest_rate": "...", "tenure": "...", "fees": "..."}}.
"sample_qa": array of 5 objects {{"question": "...", "answer": "..."}} answerable from the document.
"entities": array of {{"name": "...", "type": "Product" | "Policy" | "Regulation" | "BusinessUnit"}}.
   Products are bank products (e.g. "Home Loan"). Policies are internal policies.
   Regulations are external regulatory notices or frameworks. Use canonical short names.
"relations": array of {{"source": "...", "type": "GOVERNS" | "REQUIRES", "target": "..."}} where
   a Policy GOVERNS a Product, and a Regulation REQUIRES a Policy. Use entity names from "entities".

Use only facts in the document.
{known}
Document title: {title}

Document:
{body}
"""


def enrich(title: str, markdown: str, *, actor: str = "pipeline", known_entities: list[str] | None = None) -> Enrichment:
    body = markdown[:12000]
    known = ""
    if known_entities:
        known = (
            "Entities already in the knowledge graph — reuse these exact names when the document refers to "
            "the same thing: " + "; ".join(known_entities[:80]) + "\n"
        )
    messages = [{"role": "user", "content": PROMPT.format(title=title, body=body, known=known)}]
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            data = llm.chat_json(messages, actor=actor, purpose=f"enrich:{title}", max_tokens=2000)
            return Enrichment.model_validate(data)
        except (ValidationError, ValueError) as e:
            last_error = e
            log.warning("enrichment attempt %d invalid for %s: %s", attempt + 1, title, e)
            messages = messages + [
                {"role": "user", "content": f"Your previous answer was invalid ({str(e)[:300]}). Return valid JSON only."}
            ]
    raise ValueError(f"enrichment failed validation: {last_error}")


def normalise_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def grounded(name: str, text: str) -> bool:
    """An entity is kept only if the document actually names it — the full name, or either side of
    a "Long Name (ACRONYM)" pair. Stops the model inventing links to things the document never says."""
    hay = normalise_name(text)
    parts = [name] + [p.strip(" )") for p in name.split("(")]
    return any(len(p) > 2 and normalise_name(p) in hay for p in parts)


def ground(enrichment: "Enrichment", text: str) -> "Enrichment":
    entities = [e for e in enrichment.entities if grounded(e.name, text)]
    keep = {normalise_name(e.name) for e in entities}
    relations = [r for r in enrichment.relations if normalise_name(r.source) in keep and normalise_name(r.target) in keep]
    return enrichment.model_copy(update={"entities": entities, "relations": relations})
