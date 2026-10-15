"""Pipeline orchestration, triggered when a version is acknowledged by the custodian.

Land → Extract → Tables → Enrich → Chunk → Embed → Index (ES + Neo4j) → Activate / supersede.
Each stage is keyed by version_id and safe to re-run.
"""

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from .. import llm, storage
from ..audit import audit
from ..config import get_settings
from ..db import execute, fetch_one, jsonb, pool
from . import index_es, index_graph
from .chunk import chunk_elements
from .enrich import Enrichment, enrich, ground
from .extract import extract

log = logging.getLogger("ekb.pipeline")

# One worker: the GPU serves one enrichment at a time, and a queue keeps bulk loads orderly.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")


def submit(version_id: str, actor: str) -> None:
    execute("UPDATE document_versions SET pipeline_status = 'PENDING' WHERE version_id = %s", (version_id,))
    _executor.submit(_safe_run, version_id, actor)


def _add_catalogue_products(enrichment: Enrichment, markdown: str) -> Enrichment:
    """Policies name the products they cover; match against the product catalogue (document metadata)
    so GOVERNS links don't depend on the model spotting every product."""
    from ..db import fetch_all
    from .enrich import Entity, grounded, normalise_name

    have = {normalise_name(e.name) for e in enrichment.entities}
    extra = [
        Entity(name=r["product"], type="Product")
        for r in fetch_all("SELECT DISTINCT product FROM documents WHERE product IS NOT NULL AND product <> ''")
        if normalise_name(r["product"]) not in have and grounded(r["product"], markdown)
    ]
    return enrichment.model_copy(update={"entities": [*enrichment.entities, *extra]})


def resume_pipeline() -> None:
    """The work queue is in-process; after a restart, re-queue anything that was waiting or mid-run."""
    from ..db import fetch_all

    for row in fetch_all(
        "SELECT version_id FROM document_versions WHERE pipeline_status = 'PENDING' OR pipeline_status LIKE 'RUNNING%' "
        "ORDER BY created_at"
    ):
        submit(str(row["version_id"]), "pipeline-resume")


def _safe_run(version_id: str, actor: str) -> None:
    try:
        run(version_id, actor)
    except Exception as e:
        log.exception("pipeline failed for %s", version_id)
        execute(
            "UPDATE document_versions SET pipeline_status = 'FAILED', pipeline_error = %s WHERE version_id = %s",
            (str(e)[:2000], version_id),
        )
        audit(actor, "PIPELINE_FAILED", version_id, {"error": str(e)[:500]})


def _stage(version_id: str, stage: str) -> None:
    execute("UPDATE document_versions SET pipeline_status = %s WHERE version_id = %s", (f"RUNNING:{stage}", version_id))


def run(version_id: str, actor: str = "pipeline") -> None:
    s = get_settings()
    v = fetch_one(
        """SELECT v.*, d.title, d.country, d.business_unit, d.category, d.product, d.access_group
           FROM document_versions v JOIN documents d USING (doc_id) WHERE v.version_id = %s""",
        (version_id,),
    )
    if not v:
        raise ValueError(f"unknown version {version_id}")
    vid, doc_id = str(v["version_id"]), str(v["doc_id"])
    meta = {
        "version_id": vid,
        "doc_id": doc_id,
        "version_no": v["version_no"],
        "approval_id": str(v["approval_id"]) if v["approval_id"] else None,
        "title": v["title"],
        "country": v["country"],
        "business_unit": v["business_unit"],
        "category": v["category"],
        "product": v["product"],
        "access_group": v["access_group"],
        "effective_date": v["effective_date"].isoformat(),
        "expiry_date": v["expiry_date"].isoformat() if v["expiry_date"] else None,
    }
    audit(actor, "PIPELINE_START", vid)

    # 1. Land in the immutable raw zone
    _stage(vid, "LAND")
    data = storage.read_bytes(v["staging_uri"])
    raw_uri = storage.uri("raw", v["country"], v["business_unit"], v["category"], doc_id, f"{vid}.pdf")
    storage.write_bytes(raw_uri, data)
    execute("UPDATE document_versions SET raw_uri = %s WHERE version_id = %s", (raw_uri, vid))

    # 2. Extract
    _stage(vid, "EXTRACT")
    ext = extract(data, s.extractor)
    markdown = ext.to_markdown()
    storage.write_text(storage.uri("processed", vid, "document.md"), markdown)
    storage.write_text(storage.uri("processed", vid, "tables.json"), json.dumps(ext.tables, indent=2))

    # 3. Tables → extracted_tables (queried through the SQL engine)
    with pool().connection() as conn:
        conn.execute("DELETE FROM extracted_tables WHERE version_id = %s", (vid,))
        for t in ext.tables:
            rows = [dict(zip(t["header"], r)) for r in t["rows"]]
            conn.execute(
                "INSERT INTO extracted_tables VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), vid, t["page"], t.get("caption") or "", meta["access_group"], jsonb(rows)),
            )

    # 4. Enrich
    _stage(vid, "ENRICH")
    try:
        enrichment = enrich(
            meta["title"], markdown, actor=actor, known_entities=index_graph.known_entity_names(meta["access_group"])
        )
        enrichment = ground(enrichment, markdown)
        if meta["category"] == "Policy":
            enrichment = _add_catalogue_products(enrichment, markdown)
    except Exception as e:  # a failed enrichment should not block indexing
        log.warning("enrichment failed for %s: %s", vid, e)
        enrichment = Enrichment(summary=f"{meta['title']} (automatic summary unavailable).")
    execute("UPDATE document_versions SET enrichment = %s WHERE version_id = %s", (jsonb(enrichment.model_dump()), vid))

    # 5. Chunk
    _stage(vid, "CHUNK")
    chunks = chunk_elements(ext.elements, meta["title"])
    if not chunks:
        raise ValueError("no text could be extracted (OCR not enabled in this build)")

    # 6. Embed
    _stage(vid, "EMBED")
    vectors = llm.embed([c.indexed_text for c in chunks])

    # 7. Index
    _stage(vid, "INDEX")
    index_es.index_chunks(meta, chunks, vectors)
    graph_stats = index_graph.index_graph(meta, chunks, enrichment)
    curated = "\n".join(
        json.dumps({"chunk_id": f"{vid}:{c.seq}", "page": c.page, "heading_path": c.heading_path, "text": c.text})
        for c in chunks
    )
    storage.write_text(storage.uri("curated", vid, "chunks.jsonl"), curated)

    # 8. Activate this version, supersede the previous one everywhere
    with pool().connection() as conn:
        conn.execute(
            """UPDATE document_versions SET status = 'SUPERSEDED', is_active = false
               WHERE doc_id = %s AND version_id <> %s AND status = 'ACTIVE'""",
            (doc_id, vid),
        )
        conn.execute(
            """UPDATE document_versions SET status = 'ACTIVE', is_active = true, pipeline_status = 'DONE',
               pipeline_error = NULL, page_count = %s, chunk_count = %s WHERE version_id = %s""",
            (ext.page_count, len(chunks), vid),
        )
    index_es.deactivate_other_versions(doc_id, vid)
    index_graph.deactivate_other_versions(doc_id, vid)
    audit(
        actor,
        "PIPELINE_DONE",
        vid,
        {"pages": ext.page_count, "chunks": len(chunks), "tables": len(ext.tables), "graph": graph_stats},
    )
