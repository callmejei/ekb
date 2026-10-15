"""Guards for LLM-generated SQL — ported from Prism Sage (intelligence/sage/sql_safety.py and
guardrails/scanners/sql_guard.py) and extended with access-group trimming.

The LLM is told to write read-only SQL against a handful of curated views. Instructions are not
enforcement; this module is the gate:

1. exactly one read-only SELECT (no DDL/DML anywhere in the tree);
2. only allow-listed views — no other catalog, schema, information_schema or system tables;
3. every view reference is rewritten to a CTE that applies `access_group IN (<user's groups>)`,
   so the model cannot forget, or be talked out of, security trimming;
4. the outermost result is clamped to MAX_ROWS.
"""

import sqlglot
import sqlglot.expressions as exp

from ..config import get_settings

DIALECT = "trino"
MAX_ROWS = 500

# Every curated view carries an access_group column, so every one of them is trimmed.
ALLOWED_VIEWS = frozenset(
    {"documents", "table_rows", "table_cells", "approvals", "product_monthly", "credit_exceptions"}
)

_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.Merge, exp.Grant, exp.Command,
)
_SET_OPERATIONS = (exp.Union, exp.Intersect, exp.Except)


class UnsafeSqlError(ValueError):
    """Generated SQL was refused before reaching the engine."""


def assert_select_only(sql: str) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT, error_level=sqlglot.ErrorLevel.RAISE) if s]
    except Exception as exc:  # any parse failure is treated as unsafe
        raise UnsafeSqlError(f"SQL failed to parse: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeSqlError(f"Expected exactly one statement, got {len(statements)}.")
    root = statements[0]
    if not isinstance(root, (exp.Select, exp.Subquery, *_SET_OPERATIONS)):
        raise UnsafeSqlError(f"Statement is {type(root).__name__}, not a SELECT.")
    for node in root.walk():
        if isinstance(node, _FORBIDDEN):
            raise UnsafeSqlError(f"SQL contains a disallowed {type(node).__name__}.")
    return root


def _cte_names(root: exp.Expression) -> set[str]:
    return {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}


def _view_name(table: exp.Table) -> str:
    """Accept `view`, `kb.view` or `<catalog>.kb.view`; anything else is refused."""
    s = get_settings()
    name = table.name.lower()
    db = (table.db or "").lower()
    catalog = (table.catalog or "").lower()
    if db and db != s.sql_schema.lower():
        raise UnsafeSqlError(f"Table {table.sql()} is outside the knowledge-base views.")
    if catalog and catalog != s.sql_catalog.lower():
        raise UnsafeSqlError(f"Catalog {catalog} is not allowed.")
    if name not in ALLOWED_VIEWS:
        raise UnsafeSqlError(f"Table '{name}' is not one of the allowed views: {', '.join(sorted(ALLOWED_VIEWS))}.")
    return name


def enforce_limit(root: exp.Expression, max_rows: int = MAX_ROWS) -> exp.Expression:
    if isinstance(root, exp.Subquery) and root.this is not None:
        root.set("this", enforce_limit(root.this, max_rows))
        return root
    existing = root.args.get("limit")
    if existing is not None:
        target = existing.expression if isinstance(existing, exp.Limit) else existing
        if isinstance(target, exp.Literal) and target.is_int and int(target.name) <= max_rows:
            return root
    if isinstance(root, (exp.Select, *_SET_OPERATIONS)):
        root.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return root


def secure(sql: str, access_groups: list[str]) -> str:
    """Validate, trim to the user's access groups, and clamp. Returns the SQL to execute."""
    if not access_groups:
        raise UnsafeSqlError("User has no access groups.")
    root = assert_select_only(sql)
    s = get_settings()
    local = _cte_names(root)
    used: set[str] = set()

    for table in list(root.find_all(exp.Table)):
        bare = table.name.lower()
        if not table.db and not table.catalog and bare in local:
            continue  # reference to the query's own CTE
        view = _view_name(table)
        used.add(view)
        alias = table.alias or table.name
        table.set("this", exp.to_identifier(f"_sec_{view}"))
        table.set("db", None)
        table.set("catalog", None)
        table.set("alias", exp.TableAlias(this=exp.to_identifier(alias)))

    if not used:
        raise UnsafeSqlError("Query does not read any knowledge-base view.")

    groups = ", ".join(exp.Literal.string(g).sql() for g in access_groups)
    security_ctes = [
        exp.CTE(
            this=sqlglot.parse_one(
                f"SELECT * FROM {s.sql_catalog}.{s.sql_schema}.{view} WHERE access_group IN ({groups})",
                read=DIALECT,
            ),
            alias=exp.TableAlias(this=exp.to_identifier(f"_sec_{view}")),
        )
        for view in sorted(used)
    ]
    existing = root.args.get("with")
    if existing is not None:
        existing.set("expressions", security_ctes + list(existing.expressions))
    else:
        root.set("with", exp.With(expressions=security_ctes))
    return enforce_limit(root).sql(dialect=DIALECT)
