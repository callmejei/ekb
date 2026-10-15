"""Store clients. All store access goes through here so production clients can be swapped in."""

from functools import lru_cache
from typing import Any

from elasticsearch import Elasticsearch
from neo4j import Driver, GraphDatabase
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import get_settings


@lru_cache
def pool() -> ConnectionPool:
    s = get_settings()
    return ConnectionPool(s.pg_dsn, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=True)


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with pool().connection() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: Any = None) -> None:
    with pool().connection() as conn:
        conn.execute(sql, params)


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value)


@lru_cache
def es() -> Elasticsearch:
    return Elasticsearch(get_settings().es_url, request_timeout=60, retry_on_timeout=True, max_retries=3)


@lru_cache
def neo4j() -> Driver:
    s = get_settings()
    return GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
