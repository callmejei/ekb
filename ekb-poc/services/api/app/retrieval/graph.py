"""Knowledge-graph expansion: from the top hybrid chunks, walk 1–2 hops through mentioned entities
to related chunks in other documents. Every chunk and relationship on the path is filtered by
is_active, validity dates and the user's access groups inside the Cypher query."""

from ..db import neo4j
from ..llm import cosine
from ..security import User, cypher_params, cypher_visible
from .hybrid import fetch_chunks

EXPAND = f"""
MATCH (c:Chunk)-[m:MENTIONS]->(e)
WHERE c.chunk_id IN $ids AND {cypher_visible('m')} AND NOT e:BusinessUnit
WITH collect(DISTINCT e) AS seeds
UNWIND seeds AS s
OPTIONAL MATCH (s)-[r:GOVERNS|REQUIRES]-(n)
WHERE {cypher_visible('r')}
WITH seeds, collect(DISTINCT n) AS hop
WITH [x IN seeds + hop WHERE x IS NOT NULL] AS ents
UNWIND ents AS x
MATCH (x)<-[m2:MENTIONS]-(c2:Chunk)
WHERE {cypher_visible('m2')} AND {cypher_visible('c2')} AND NOT c2.chunk_id IN $ids
RETURN c2.chunk_id AS chunk_id, count(DISTINCT x) AS strength, collect(DISTINCT x.name)[..4] AS via
ORDER BY strength DESC
LIMIT 25
"""

CONTEXT = f"""
MATCH (c:Chunk)-[m:MENTIONS]->(e)
WHERE c.chunk_id IN $ids AND {cypher_visible('m')} AND NOT e:BusinessUnit
WITH DISTINCT e
OPTIONAL MATCH (e)-[r:GOVERNS|REQUIRES]-(n)
WHERE {cypher_visible('r')}
OPTIONAL MATCH (ev:Chunk)-[em:MENTIONS]->(t)
WHERE r IS NOT NULL AND t = endNode(r) AND ev.version_id = r.version_id AND {cypher_visible('ev')}
WITH e, r, ev ORDER BY ev.page, ev.chunk_id
WITH e, r, collect(ev.chunk_id)[0] AS evidence
RETURN e.name AS name, labels(e)[0] AS type,
       collect(CASE WHEN r IS NULL THEN NULL ELSE
         {{source: startNode(r).name, rel: type(r), target: endNode(r).name, evidence: evidence}} END) AS relations
LIMIT 20
"""


def expand(seed_ids: list[str], vector: list[float], user: User, limit: int) -> tuple[list[dict], dict]:
    params = {"ids": seed_ids, **cypher_params(user)}
    with neo4j().session() as s:
        candidates = [r.data() for r in s.run(EXPAND, params)]
        context_rows = [r.data() for r in s.run(CONTEXT, params)]

    via = {c["chunk_id"]: c["via"] for c in candidates}
    relations, seen = [], set()
    for row in context_rows:
        for rel in row["relations"]:
            key = (rel["source"], rel["rel"], rel["target"])
            if key not in seen:
                seen.add(key)
                relations.append(rel)
    entities = [{"name": r["name"], "type": r["type"]} for r in context_rows]

    # Evidence chunks back each graph fact so the answer can cite it; fetched under the same
    # security filter, so a fact whose evidence the user cannot see is dropped.
    evidence_ids = [r["evidence"] for r in relations if r.get("evidence") and r["evidence"] not in seed_ids]
    evidence_ids = list(dict.fromkeys(evidence_ids))[:3]
    candidate_ids = [c["chunk_id"] for c in candidates if c["chunk_id"] not in evidence_ids]
    fetched = {c["chunk_id"]: c for c in fetch_chunks(evidence_ids + candidate_ids, user)}
    relations = [r for r in relations if not r.get("evidence") or r["evidence"] in fetched or r["evidence"] in seed_ids]

    for ch in fetched.values():
        emb = ch.pop("embedding", None)
        ch["graph_similarity"] = round(cosine(vector, emb), 4) if emb else 0.0
        ch["origin"] = "graph"
        ch["via"] = via.get(ch["chunk_id"], [])
    evidence = [fetched[i] for i in evidence_ids if i in fetched]
    for ch in evidence:
        ch["via"] = ch["via"] or [r["source"] for r in relations if r.get("evidence") == ch["chunk_id"]][:2]
    similar = sorted((fetched[i] for i in candidate_ids if i in fetched), key=lambda c: -c["graph_similarity"])
    return evidence + similar[:limit], {"entities": entities, "relations": relations}
