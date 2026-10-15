"""Idempotent creation of the Elasticsearch index/alias and Neo4j constraints at API start."""

import logging
import time

from .config import get_settings
from .db import es, neo4j

log = logging.getLogger("ekb.bootstrap")

ES_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "version_id": {"type": "keyword"},
            "version_no": {"type": "integer"},
            "approval_id": {"type": "keyword"},
            "title": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "heading_path": {"type": "text"},
            "chunk_text": {"type": "text"},
            "chunk_type": {"type": "keyword"},
            "embedding": {
                "type": "dense_vector",
                "dims": 1024,
                "index": True,
                "similarity": "cosine",
                "index_options": {"type": "int8_hnsw"},
            },
            "page": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "country": {"type": "keyword"},
            "business_unit": {"type": "keyword"},
            "category": {"type": "keyword"},
            "product": {"type": "keyword"},
            "effective_date": {"type": "date"},
            "expiry_date": {"type": "date"},
            "access_group": {"type": "keyword"},
        }
    },
}

CONSTRAINTS = [
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT doc_version IF NOT EXISTS FOR (d:Document) REQUIRE d.version_id IS UNIQUE",
    "CREATE CONSTRAINT product_key IF NOT EXISTS FOR (e:Product) REQUIRE e.key IS UNIQUE",
    "CREATE CONSTRAINT policy_key IF NOT EXISTS FOR (e:Policy) REQUIRE e.key IS UNIQUE",
    "CREATE CONSTRAINT regulation_key IF NOT EXISTS FOR (e:Regulation) REQUIRE e.key IS UNIQUE",
    "CREATE CONSTRAINT bu_key IF NOT EXISTS FOR (e:BusinessUnit) REQUIRE e.key IS UNIQUE",
    "CREATE INDEX doc_id IF NOT EXISTS FOR (d:Document) ON (d.doc_id)",
]


def ensure_es() -> None:
    s = get_settings()
    client = es()
    if not client.indices.exists(index=s.es_index):
        client.indices.create(index=s.es_index, **ES_MAPPING)
        log.info("created index %s", s.es_index)
    if not client.indices.exists_alias(name=s.es_index_alias):
        client.indices.put_alias(index=s.es_index, name=s.es_index_alias)


def ensure_neo4j() -> None:
    with neo4j().session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)


def bootstrap(retries: int = 30) -> None:
    for i in range(retries):
        try:
            ensure_es()
            ensure_neo4j()
            return
        except Exception as e:  # stores may still be warming up
            log.warning("bootstrap attempt %d failed: %s", i + 1, e)
            time.sleep(3)
    raise RuntimeError("could not bootstrap Elasticsearch/Neo4j")
