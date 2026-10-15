import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .. import llm
from ..audit import audit
from ..config import get_settings
from ..db import es, execute, fetch_all
from ..retrieval import answer, data, graph, hybrid, router as question_router
from ..security import User, current_user, es_mandatory_filter

router = APIRouter(prefix="/api", tags=["query"])

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="query")


class Ask(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    mode: str = "hybrid_graph"  # hybrid | hybrid_graph
    route: str = "auto"  # auto | document | data | mixed


def _documents(question: str, mode: str, user: User, timings: dict) -> tuple[list[dict], dict]:
    s = get_settings()
    t = time.perf_counter()
    vector = llm.embed([question])[0]
    timings["embed"] = int((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    top = hybrid.rerank(question, hybrid.hybrid_search(question, vector, user), s.final_top_k)
    timings["hybrid"] = int((time.perf_counter() - t) * 1000)
    graph_ctx: dict = {"entities": [], "relations": []}
    extra: list[dict] = []
    if mode == "hybrid_graph" and top:
        t = time.perf_counter()
        extra, graph_ctx = graph.expand([h["chunk_id"] for h in top], vector, user, s.graph_extra_chunks)
        timings["graph"] = int((time.perf_counter() - t) * 1000)
    return top + extra, graph_ctx


def _data(question: str, user: User, trace_id: str, timings: dict) -> data.DataResult:
    t = time.perf_counter()
    res = data.answer_question(question, user, trace_id)
    timings["sql"] = int((time.perf_counter() - t) * 1000)
    return res


@router.post("/query")
def ask(body: Ask, user: User = Depends(current_user)):
    s = get_settings()
    trace_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    timings: dict[str, int] = {}

    if body.route in question_router.ROUTES:
        r, reason = body.route, "chosen by user"
    else:
        t = time.perf_counter()
        r, reason = question_router.route(body.question, user)
        timings["route"] = int((time.perf_counter() - t) * 1000)

    context: list[dict] = []
    graph_ctx: dict = {"entities": [], "relations": []}
    data_res: data.DataResult | None = None

    # Mixed questions run both paths concurrently.
    doc_future = _pool.submit(_documents, body.question, body.mode, user, timings) if r in ("document", "mixed") else None
    data_future = _pool.submit(_data, body.question, user, trace_id, timings) if r in ("data", "mixed") else None
    if doc_future:
        context, graph_ctx = doc_future.result()
    if data_future:
        data_res = data_future.result()

    t = time.perf_counter()
    citations: list[dict] = []
    if r == "data" and data_res is not None:
        text = data.write_answer(body.question, data_res, user, trace_id)
    else:
        data_block = None
        if data_res is not None and data_res.sql and not data_res.error:
            data_block = f"What the query returns: {data_res.summary}\n{data.rows_for_llm(data_res)}"
        text, citations = answer.generate(
            body.question,
            context,
            actor=user.username,
            trace_id=trace_id,
            relations=graph_ctx["relations"],
            data_block=data_block,
        )
    timings["generate"] = int((time.perf_counter() - t) * 1000)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    retrieved = [
        {
            "chunk_id": c["chunk_id"],
            "title": c["title"],
            "version_no": c.get("version_no"),
            "page": c["page"],
            "heading_path": c["heading_path"],
            "origin": c.get("origin"),
            "score": c.get("score"),
            "ranks": c.get("ranks"),
            "via": c.get("via"),
            "access_group": c["access_group"],
        }
        for c in context
    ]
    audit(
        user.username,
        "QUERY",
        trace_id,
        {
            "question": body.question,
            "route": r,
            "route_reason": reason,
            "mode": body.mode,
            "chunk_ids": [c["chunk_id"] for c in context],
            "sql": data_res.executed_sql if data_res else None,
            "model": s.llm_model,
            "latency_ms": latency_ms,
            "access_groups": list(user.access_groups),
        },
    )
    return {
        "trace_id": trace_id,
        "answer": text,
        "citations": citations,
        "route": r,
        "route_reason": reason,
        "mode": body.mode,
        "sql": data_res.sql if data_res else None,
        "data": data.to_response(data_res) if data_res else None,
        "graph": graph_ctx,
        "retrieved": retrieved,
        "latency_ms": latency_ms,
        "timings": timings,
        "model": s.llm_model,
    }


class Feedback(BaseModel):
    trace_id: str
    rating: int
    comment: str | None = None


@router.post("/feedback")
def feedback(body: Feedback, user: User = Depends(current_user)):
    execute(
        "INSERT INTO feedback (username, trace_id, rating, comment) VALUES (%s, %s, %s, %s)",
        (user.username, body.trace_id, 1 if body.rating > 0 else -1, body.comment),
    )
    audit(user.username, "FEEDBACK", body.trace_id, {"rating": body.rating, "comment": body.comment})
    return {"ok": True}


@router.get("/browse")
def browse(
    category: str | None = None,
    product: str | None = None,
    business_unit: str | None = None,
    q: str | None = Query(None, max_length=200),
    user: User = Depends(current_user),
):
    """Faceted browse over active, in-date documents the user may see (Elasticsearch facets)."""
    filters = es_mandatory_filter(user)
    for field, value in (("category", category), ("product", product), ("business_unit", business_unit)):
        if value:
            filters.append({"term": {field: value}})
    must = [{"multi_match": {"query": q, "fields": ["chunk_text", "title^2", "heading_path"]}}] if q else []
    res = es().search(
        index=get_settings().es_index_alias,
        size=0,
        query={"bool": {"filter": filters, "must": must}},
        aggs={
            "category": {"terms": {"field": "category", "size": 20}},
            "product": {"terms": {"field": "product", "size": 30}},
            "business_unit": {"terms": {"field": "business_unit", "size": 20}},
            "docs": {
                "terms": {"field": "version_id", "size": 200},
                "aggs": {"top": {"top_hits": {"size": 1, "_source": {"excludes": ["embedding", "chunk_text"]}}}},
            },
        },
    )
    aggs = res["aggregations"]
    facets = {k: [{"value": b["key"], "count": b["doc_count"]} for b in aggs[k]["buckets"]] for k in ("category", "product", "business_unit")}
    version_ids = [b["key"] for b in aggs["docs"]["buckets"]]
    summaries = {}
    if version_ids:
        for row in fetch_all(
            "SELECT version_id::text AS vid, enrichment FROM document_versions WHERE version_id::text = ANY(%s)",
            (version_ids,),
        ):
            summaries[row["vid"]] = row["enrichment"] or {}
    docs = []
    for b in aggs["docs"]["buckets"]:
        src = b["top"]["hits"]["hits"][0]["_source"]
        e = summaries.get(b["key"], {})
        docs.append(
            {
                "version_id": src["version_id"],
                "doc_id": src["doc_id"],
                "title": src["title"],
                "version_no": src.get("version_no"),
                "category": src["category"],
                "product": src["product"],
                "business_unit": src["business_unit"],
                "access_group": src["access_group"],
                "effective_date": src["effective_date"],
                "expiry_date": src.get("expiry_date"),
                "matches": b["doc_count"],
                "summary": e.get("summary"),
                "key_info": e.get("key_info", {}),
                "sample_qa": e.get("sample_qa", []),
                "entities": e.get("entities", []),
            }
        )
    docs.sort(key=lambda d: d["title"])
    return {"facets": facets, "documents": docs}
