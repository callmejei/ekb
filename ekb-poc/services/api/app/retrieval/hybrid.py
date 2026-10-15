"""Elasticsearch hybrid search: BM25 + kNN, both under the mandatory security filter, merged
with reciprocal rank fusion (in Python unless ES_USE_NATIVE_RRF=true)."""

from ..config import get_settings
from ..db import es
from ..security import User, es_mandatory_filter

SOURCE_EXCLUDES = ["embedding"]


def bm25(question: str, user: User, size: int) -> list[dict]:
    res = es().search(
        index=get_settings().es_index_alias,
        size=size,
        query={
            "bool": {
                "must": {
                    "multi_match": {
                        "query": question,
                        "fields": ["chunk_text", "heading_path^1.5", "title^2"],
                    }
                },
                "filter": es_mandatory_filter(user),
            }
        },
        source_excludes=SOURCE_EXCLUDES,
    )
    return res["hits"]["hits"]


def knn(vector: list[float], user: User, k: int, candidates: int) -> list[dict]:
    res = es().search(
        index=get_settings().es_index_alias,
        size=k,
        knn={
            "field": "embedding",
            "query_vector": vector,
            "k": k,
            "num_candidates": candidates,
            # Security filter inside kNN — never post-filtered.
            "filter": {"bool": {"filter": es_mandatory_filter(user)}},
        },
        source_excludes=SOURCE_EXCLUDES,
    )
    return res["hits"]["hits"]


def rrf(*ranked_lists: list[dict], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}
    ranks: dict[str, dict[str, int]] = {}
    for li, hits in enumerate(ranked_lists):
        for rank, h in enumerate(hits, start=1):
            cid = h["_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            docs.setdefault(cid, h["_source"])
            ranks.setdefault(cid, {})[["bm25", "knn"][li] if li < 2 else str(li)] = rank
    ordered = sorted(scores, key=lambda c: -scores[c])
    return [{**docs[c], "score": round(scores[c], 5), "ranks": ranks[c], "origin": "hybrid"} for c in ordered]


def hybrid_search(question: str, vector: list[float], user: User) -> list[dict]:
    s = get_settings()
    return rrf(bm25(question, user, s.knn_k), knn(vector, user, s.knn_k, s.knn_candidates), k=s.rrf_k)


def fetch_chunks(chunk_ids: list[str], user: User) -> list[dict]:
    """Fetch chunks by id — still under the mandatory filter, so graph results can't leak."""
    if not chunk_ids:
        return []
    res = es().search(
        index=get_settings().es_index_alias,
        size=len(chunk_ids),
        query={"bool": {"filter": [{"ids": {"values": chunk_ids}}, *es_mandatory_filter(user)]}},
    )
    return [h["_source"] for h in res["hits"]["hits"]]


def rerank(question: str, hits: list[dict], top_k: int) -> list[dict]:
    """Cross-encoder rerank (bge-reranker-v2-m3) when RERANK_ENABLED; otherwise RRF order."""
    s = get_settings()
    if not s.rerank_enabled or not hits:
        return hits[:top_k]
    from sentence_transformers import CrossEncoder  # optional dependency

    model = _cross_encoder(s.rerank_model, CrossEncoder)
    scores = model.predict([(question, f"{h['heading_path']}\n{h['chunk_text']}") for h in hits])
    for h, sc in zip(hits, scores):
        h["rerank_score"] = float(sc)
    return sorted(hits, key=lambda h: -h["rerank_score"])[:top_k]


_ce = None


def _cross_encoder(name, cls):
    global _ce
    if _ce is None:
        _ce = cls(name)
    return _ce
