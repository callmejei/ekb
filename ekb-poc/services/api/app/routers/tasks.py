from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import workflow
from ..db import fetch_all
from ..security import User, current_user

router = APIRouter(prefix="/api/tasks", tags=["workflow"])


class Decision(BaseModel):
    decision: str
    comment: str | None = None


@router.get("")
def pending_tasks(user: User = Depends(current_user)):
    roles = ["STEWARD", "OWNER", "CUSTODIAN"] if "ADMIN" in user.roles else list(user.roles)
    rows = fetch_all(
        """SELECT t.task_id, t.step, t.role, t.batch_id, t.created_at,
                  v.version_id, v.version_no, v.file_name, v.effective_date, v.expiry_date, v.conflict,
                  v.uploaded_by, v.status, v.created_at AS uploaded_at,
                  d.doc_id, d.title, d.country, d.business_unit, d.category, d.product, d.access_group
           FROM workflow_tasks t
           JOIN document_versions v USING (version_id)
           JOIN documents d USING (doc_id)
           WHERE t.decision IS NULL AND t.role = ANY(%s) AND d.access_group = ANY(%s)
           ORDER BY t.created_at""",
        (roles, list(user.access_groups)),
    )
    for r in rows:
        r["self_upload"] = r["uploaded_by"] == user.username
    return rows


@router.post("/{task_id}/decision")
def decide(task_id: str, body: Decision, user: User = Depends(current_user)):
    return workflow.decide(user, task_id, body.decision, body.comment)


@router.post("/batch/{batch_id}/decision")
def decide_batch(batch_id: str, body: Decision, user: User = Depends(current_user)):
    return workflow.decide_batch(user, batch_id, body.decision, body.comment)
