from fastapi import APIRouter, Depends, HTTPException

from ..db import es, fetch_all, fetch_one, neo4j
from ..config import get_settings
from ..security import User, current_user

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/users")
def users():
    """Local login stand-in: the seeded users. Replaced by Keycloak/bank IdP in production."""
    return fetch_all("SELECT username, display_name, roles, access_groups FROM users ORDER BY username")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "username": user.username,
        "display_name": user.display_name,
        "roles": list(user.roles),
        "access_groups": list(user.access_groups),
    }


@router.get("/audit")
def audit_log(limit: int = 300, action: str | None = None, user: User = Depends(current_user)):
    if "ADMIN" not in user.roles:
        raise HTTPException(403, "Audit log is restricted to administrators")
    if action:
        return fetch_all(
            "SELECT * FROM audit_log WHERE action = %s ORDER BY audit_id DESC LIMIT %s", (action, min(limit, 2000))
        )
    return fetch_all("SELECT * FROM audit_log ORDER BY audit_id DESC LIMIT %s", (min(limit, 2000),))


@router.get("/stats")
def stats(user: User = Depends(current_user)):
    groups = list(user.access_groups)
    counts = fetch_one(
        """SELECT count(*) FILTER (WHERE v.status = 'ACTIVE') AS active,
                  count(*) FILTER (WHERE v.status IN ('SUBMITTED','VERIFIED','APPROVED')) AS in_review,
                  count(*) FILTER (WHERE v.status = 'ACKNOWLEDGED') AS indexing,
                  count(*) FILTER (WHERE v.status = 'SUPERSEDED') AS superseded
           FROM document_versions v JOIN documents d USING (doc_id) WHERE d.access_group = ANY(%s)""",
        (groups,),
    )
    pending = fetch_one(
        """SELECT count(*) AS n FROM workflow_tasks t JOIN document_versions v USING (version_id)
           JOIN documents d USING (doc_id)
           WHERE t.decision IS NULL AND t.role = ANY(%s) AND d.access_group = ANY(%s)""",
        (["STEWARD", "OWNER", "CUSTODIAN"] if "ADMIN" in user.roles else list(user.roles), groups),
    )
    chunks = es().count(index=get_settings().es_index_alias, query={"term": {"is_active": True}})["count"]
    with neo4j().session() as s:
        g = s.run(
            "MATCH (n) WHERE n:Product OR n:Policy OR n:Regulation OR n:BusinessUnit RETURN count(n) AS entities"
        ).single()
    return {**counts, "pending_tasks": pending["n"], "indexed_chunks": chunks, "graph_entities": g["entities"]}
