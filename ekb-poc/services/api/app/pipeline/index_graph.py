"""Load documents, chunks, entities and relationships into Neo4j.

Entity nodes (Product, Policy, Regulation, BusinessUnit) are shared across documents, so they
carry no access group of their own. Visibility is enforced on what links to them: Chunk nodes and
every relationship carry doc_id, version_id, access_group and is_active, and query-time traversal
filters on those.
"""

from ..db import neo4j
from .chunk import Chunk
from .enrich import Enrichment, normalise_name

LABELS = {"Product", "Policy", "Regulation", "BusinessUnit"}


def _key(name: str, etype: str) -> str:
    return f"{normalise_name(name)}|{etype}"


def known_entity_names(access_group: str) -> list[str]:
    """Names already in the graph, but only those mentioned by documents in the same access group —
    so a restricted entity name can never be suggested while enriching a more widely visible document."""
    with neo4j().session() as s:
        rows = s.run(
            "MATCH (c:Chunk {access_group: $g})-[:MENTIONS]->(e) WHERE e:Product OR e:Policy OR e:Regulation "
            "RETURN DISTINCT e.name AS name, labels(e)[0] AS type ORDER BY name LIMIT 150",
            g=access_group,
        )
        return [f"{r['name']} ({r['type']})" for r in rows]


# Allowed relationship shapes: (relationship, source type, target type).
SHAPES = {("GOVERNS", "Policy", "Product"), ("REQUIRES", "Regulation", "Policy")}


def _relations(meta: dict, entities: dict[str, dict], enrichment: Enrichment) -> set[tuple[str, str, str]]:
    """LLM relations, corrected to the allowed shapes, plus deterministic links for policy documents:
    the policy GOVERNS every product it mentions, and every regulation it cites REQUIRES it."""
    by_name = {normalise_name(e["name"]): e for e in entities.values()}
    out: set[tuple[str, str, str]] = set()
    for r in enrichment.relations:
        a, b = by_name.get(normalise_name(r.source)), by_name.get(normalise_name(r.target))
        if not a or not b:
            continue
        for rel, src_t, tgt_t in SHAPES:
            if (a["type"], b["type"]) == (src_t, tgt_t):
                out.add((a["key"], rel, b["key"]))
            elif (b["type"], a["type"]) == (src_t, tgt_t):
                out.add((b["key"], rel, a["key"]))
    if meta["category"] == "Policy":
        policy_key = _key(meta["title"], "Policy")
        for e in entities.values():
            if e["type"] == "Product":
                out.add((policy_key, "GOVERNS", e["key"]))
            elif e["type"] == "Regulation":
                out.add((e["key"], "REQUIRES", policy_key))
    return out


def index_graph(meta: dict, chunks: list[Chunk], enrichment: Enrichment) -> dict:
    vid = meta["version_id"]
    lineage = {
        "doc_id": meta["doc_id"],
        "version_id": vid,
        "access_group": meta["access_group"],
        "is_active": True,
        "effective_date": meta["effective_date"],
        "expiry_date": meta["expiry_date"],
        "approval_id": meta["approval_id"],
    }
    chunk_rows = [
        {"chunk_id": f"{vid}:{c.seq}", "page": c.page, "heading_path": c.heading_path, "text": c.indexed_text.lower()}
        for c in chunks
    ]
    entities = {}
    for e in enrichment.entities:
        if e.type in LABELS:
            entities[_key(e.name, e.type)] = {"key": _key(e.name, e.type), "name": e.name.strip(), "type": e.type}
    # The owning business unit is always an entity, even if the model missed it.
    bu = {"key": _key(meta["business_unit"], "BusinessUnit"), "name": meta["business_unit"], "type": "BusinessUnit"}
    entities[bu["key"]] = bu
    if meta["category"] == "Policy":  # a policy document is itself a Policy entity
        pk = _key(meta["title"], "Policy")
        entities[pk] = {"key": pk, "name": meta["title"], "type": "Policy"}
    if meta.get("product"):
        pk = _key(meta["product"], "Product")
        entities.setdefault(pk, {"key": pk, "name": meta["product"], "type": "Product"})

    with neo4j().session() as s:
        # Re-runs replace this version's links rather than accumulating stale ones.
        s.run("MATCH ()-[r]->() WHERE r.version_id = $vid AND type(r) <> 'SUPERSEDES' DELETE r", vid=vid)
        s.run(
            """
            MERGE (d:Document {version_id: $vid})
            SET d += $lineage, d.title = $title, d.version_no = $version_no,
                d.category = $category, d.product = $product
            WITH d
            MERGE (b:BusinessUnit {key: $bu.key}) ON CREATE SET b.name = $bu.name
            MERGE (d)-[o:OWNED_BY]->(b) SET o += $lineage
            """,
            vid=vid,
            lineage=lineage,
            title=meta["title"],
            version_no=meta["version_no"],
            category=meta["category"],
            product=meta["product"],
            bu=bu,
        )
        s.run(
            """
            MATCH (d:Document {version_id: $vid})
            UNWIND $chunks AS row
            MERGE (c:Chunk {chunk_id: row.chunk_id})
            SET c += $lineage, c.page = row.page, c.heading_path = row.heading_path, c.title = $title
            MERGE (d)-[h:HAS_CHUNK]->(c) SET h += $lineage
            """,
            vid=vid,
            chunks=chunk_rows,
            lineage=lineage,
            title=meta["title"],
        )
        mentions = 0
        for ent in entities.values():
            label = ent["type"]
            s.run(f"MERGE (e:{label} {{key: $key}}) ON CREATE SET e.name = $name", key=ent["key"], name=ent["name"])
            needle = normalise_name(ent["name"])
            hits = [r["chunk_id"] for r in chunk_rows if needle in r["text"]]
            if not hits and chunk_rows:
                hits = [chunk_rows[0]["chunk_id"]]  # document-level mention
            s.run(
                f"""
                MATCH (e:{label} {{key: $key}})
                UNWIND $ids AS cid
                MATCH (c:Chunk {{chunk_id: cid}})
                MERGE (c)-[m:MENTIONS]->(e) SET m += $lineage
                """,
                key=ent["key"],
                ids=hits,
                lineage=lineage,
            )
            mentions += len(hits)

        rels = 0
        for src_key, rel, tgt_key in _relations(meta, entities, enrichment):
            src, tgt = entities[src_key], entities[tgt_key]
            s.run(
                f"""
                MATCH (a:{src['type']} {{key: $a}}), (b:{tgt['type']} {{key: $b}})
                MERGE (a)-[r:{rel} {{version_id: $vid}}]->(b) SET r += $lineage
                """,
                a=src_key,
                b=tgt_key,
                vid=vid,
                lineage=lineage,
            )
            rels += 1

        s.run(
            """
            MATCH (d:Document {version_id: $vid}), (old:Document {doc_id: $doc_id})
            WHERE old.version_id <> $vid AND old.version_no < d.version_no
            MERGE (d)-[r:SUPERSEDES]->(old) SET r += $lineage
            """,
            vid=vid,
            doc_id=meta["doc_id"],
            lineage=lineage,
        )
    return {"entities": len(entities), "mentions": mentions, "relations": rels}


def deactivate_other_versions(doc_id: str, keep_version_id: str) -> None:
    with neo4j().session() as s:
        s.run(
            "MATCH (n) WHERE n.doc_id = $doc_id AND n.version_id <> $vid SET n.is_active = false",
            doc_id=doc_id,
            vid=keep_version_id,
        )
        s.run(
            "MATCH ()-[r]->() WHERE r.doc_id = $doc_id AND r.version_id <> $vid "
            "AND type(r) <> 'SUPERSEDES' SET r.is_active = false",
            doc_id=doc_id,
            vid=keep_version_id,
        )
