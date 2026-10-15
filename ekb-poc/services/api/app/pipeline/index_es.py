"""Bulk index chunks into Elasticsearch and deactivate superseded versions."""

from elasticsearch import helpers

from ..config import get_settings
from ..db import es
from .chunk import Chunk


def index_chunks(meta: dict, chunks: list[Chunk], vectors: list[list[float]]) -> int:
    s = get_settings()
    actions = []
    for c, vec in zip(chunks, vectors):
        chunk_id = f"{meta['version_id']}:{c.seq}"
        actions.append(
            {
                "_index": s.es_index_alias,
                "_id": chunk_id,
                "_source": {
                    "chunk_id": chunk_id,
                    "doc_id": meta["doc_id"],
                    "version_id": meta["version_id"],
                    "version_no": meta["version_no"],
                    "approval_id": meta["approval_id"],
                    "title": meta["title"],
                    "heading_path": c.heading_path,
                    "chunk_text": c.text,
                    "chunk_type": c.chunk_type,
                    "embedding": vec,
                    "page": c.page,
                    "is_active": True,
                    "country": meta["country"],
                    "business_unit": meta["business_unit"],
                    "category": meta["category"],
                    "product": meta["product"],
                    "effective_date": meta["effective_date"],
                    "expiry_date": meta["expiry_date"],
                    "access_group": meta["access_group"],
                },
            }
        )
    ok, _ = helpers.bulk(es(), actions, refresh="wait_for")
    return ok


def deactivate_other_versions(doc_id: str, keep_version_id: str) -> None:
    es().update_by_query(
        index=get_settings().es_index_alias,
        query={
            "bool": {
                "filter": [{"term": {"doc_id": doc_id}}],
                "must_not": [{"term": {"version_id": keep_version_id}}],
            }
        },
        script={"source": "ctx._source.is_active = false", "lang": "painless"},
        refresh=True,
        conflicts="proceed",
    )
