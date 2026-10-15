"""SQL guard: read-only, allow-listed views only, access groups injected, LIMIT clamped."""

import pytest

from app.retrieval.sql_guard import UnsafeSqlError, secure

GROUPS = ["RETAIL_PRODUCTS"]


def test_access_filter_injected_for_every_view():
    sql = secure("SELECT d.title, c.cell_value FROM documents d JOIN kb.table_cells c ON d.version_id = c.version_id", GROUPS)
    assert sql.count("access_group IN ('RETAIL_PRODUCTS')") == 2
    assert "FROM postgresql.kb.documents" in sql and "FROM postgresql.kb.table_cells" in sql
    assert sql.endswith("LIMIT 500")


def test_model_cte_cannot_bypass_filter():
    sql = secure("WITH x AS (SELECT * FROM credit_exceptions) SELECT sum(exceptions) FROM x", GROUPS)
    assert "_sec_credit_exceptions AS (SELECT * FROM postgresql.kb.credit_exceptions WHERE access_group IN" in sql
    assert sql.index("_sec_credit_exceptions AS") < sql.index("x AS")


def test_smaller_limit_respected_larger_clamped():
    assert secure("SELECT title FROM documents LIMIT 5", GROUPS).endswith("LIMIT 5")
    assert secure("SELECT title FROM documents LIMIT 100000", GROUPS).endswith("LIMIT 500")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM documents",
        "SELECT 1; DROP TABLE documents",
        "SELECT * FROM postgresql.public.documents",
        "SELECT * FROM users",
        "SELECT * FROM system.runtime.queries",
        "SELECT * FROM information_schema.tables",
        "SELECT 1",
    ],
)
def test_refused(sql):
    with pytest.raises(UnsafeSqlError):
        secure(sql, GROUPS)


def test_no_groups_refused():
    with pytest.raises(UnsafeSqlError):
        secure("SELECT title FROM documents", [])
