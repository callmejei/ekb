"""All configuration comes from environment variables (.env), so every local component
can be swapped for its production counterpart without code changes."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Storage
    lake_uri: str = "s3://ekb-lake"
    s3_endpoint_url: str | None = "http://minio:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # PostgreSQL
    pg_host: str = "postgres"
    pg_port: int = 5432
    pg_db: str = "ekb"
    pg_user: str = "ekb"
    pg_password: str = ""

    # SQL engine (Trino locally, Starburst in production)
    sql_engine_url: str = "http://trino:8080"
    sql_catalog: str = "postgresql"
    sql_schema: str = "kb"

    # Elasticsearch
    es_url: str = "http://elasticsearch:9200"
    es_index: str = "ekb-chunks-v1"
    es_index_alias: str = "ekb-chunks"
    es_use_native_rrf: bool = False

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # LLM
    llm_base_url: str = "http://ollama:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = ""  # empty for Ollama/vLLM; set for a hosted OpenAI-compatible endpoint
    embed_base_url: str | None = None  # defaults to llm_base_url; keep embeddings local when the LLM is hosted
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # Workflow / pipeline
    workflow_engine: str = "builtin"
    near_dup_threshold: float = 0.95
    extractor: str = "pymupdf"

    # Retrieval
    knn_k: int = 50
    knn_candidates: int = 200
    rrf_k: int = 60
    final_top_k: int = 8
    graph_extra_chunks: int = 3

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.pg_user} password={self.pg_password}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
