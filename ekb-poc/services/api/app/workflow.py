"""Built-in maker-checker workflow (WORKFLOW_ENGINE=builtin), same states and steps as the
Flowable process: Upload (Requestor) → Verify (Steward) → Approve (Owner) → Acknowledge (Custodian).
"""

import hashlib
import re
import uuid
from datetime import date

from fastapi import HTTPException

from . import llm, storage
from .audit import audit
from .config import get_settings
from .db import fetch_all, fetch_one, jsonb, pool
from .pipeline import run as pipeline
from .pipeline.extract import full_text, probe_text
from .security import User

NEXT_STEP = {
    "VERIFY": ("VERIFIED", "APPROVE", "OWNER"),
    "APPROVE": ("APPROVED", "ACKNOWLEDGE", "CUSTODIAN"),
    "ACKNOWLEDGE": ("ACKNOWLEDGED", None, None),
}


class DuplicateError(HTTPException):
    def __init__(self, match: dict):
        super().__init__(
            409,
            {
                "error": "exact_duplicate",
                "message": f"This file is identical to '{match['title']}' v{match['version_no']} ({match['status']}).",
                "match": {k: str(v) for k, v in match.items()},
            },
        )


def _shingles(text: str, n: int = 3) -> set[str]:
    words = re.findall(r"[a-z0-9.%]+", text.lower())
    return {" ".join(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _near_duplicates(data: bytes, vector: list[float], category: str, exclude_doc: str | None) -> list[dict]:
    """Two signals: word-shingle Jaccard (near-identical wording) and BGE-M3 cosine (same meaning).
    Either crossing its threshold flags a near-duplicate for the steward."""
    rows = fetch_all(
        """SELECT v.version_id, v.doc_id, v.version_no, v.probe_embedding, v.raw_uri, v.staging_uri, d.title
           FROM document_versions v JOIN documents d USING (doc_id)
           WHERE v.is_active AND d.category = %s""",
        (category,),
    )
    mine = _shingles(full_text(data))
    threshold = get_settings().near_dup_threshold
    hits = []
    for r in rows:
        if exclude_doc and str(r["doc_id"]) == exclude_doc:
            continue  # a new version of the same document is expected to be similar
        cos = llm.cosine(vector, list(r["probe_embedding"])) if r["probe_embedding"] else 0.0
        jac = _jaccard(mine, _shingles(full_text(storage.read_bytes(r["raw_uri"] or r["staging_uri"]))))
        if jac >= 0.8 or cos >= threshold:
            flag = "near_duplicate"
        elif jac >= 0.5 or cos >= threshold - 0.07:
            flag = "similar"
        else:
            continue
        hits.append(
            {
                "doc_id": str(r["doc_id"]),
                "version_id": str(r["version_id"]),
                "title": r["title"],
                "version_no": r["version_no"],
                "similarity": round(max(jac, cos), 4),
                "text_overlap": round(jac, 4),
                "semantic": round(cos, 4),
                "flag": flag,
            }
        )
    return sorted(hits, key=lambda h: -h["similarity"])[:5]


def upload(
    user: User,
    *,
    data: bytes,
    file_name: str,
    title: str,
    country: str,
    business_unit: str,
    category: str,
    product: str | None,
    access_group: str,
    effective_date: date,
    expiry_date: date | None,
    doc_id: str | None = None,
    batch_id: str | None = None,
) -> dict:
    if not user.has_role("REQUESTOR"):
        raise HTTPException(403, "Only a Requestor can upload documents")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are accepted in the POC")
    if access_group not in user.access_groups:
        raise HTTPException(403, f"You cannot publish into access group {access_group}")

    sha = hashlib.sha256(data).hexdigest()
    dup = fetch_one(
        """SELECT d.title, v.version_no, v.status, v.version_id, d.doc_id
           FROM document_versions v JOIN documents d USING (doc_id)
           WHERE v.file_sha256 = %s AND v.status NOT IN ('REJECTED', 'RETURNED') LIMIT 1""",
        (sha,),
    )
    if dup:
        audit(user.username, "DUPLICATE_BLOCKED", str(dup["version_id"]), {"file": file_name, "sha256": sha})
        raise DuplicateError(dup)

    version_id = str(uuid.uuid4())
    if doc_id:
        doc = fetch_one("SELECT * FROM documents WHERE doc_id = %s", (doc_id,))
        if not doc:
            raise HTTPException(404, "Unknown document for new version")
        category, access_group = doc["category"], doc["access_group"]
        version_no = fetch_one("SELECT max(version_no) AS n FROM document_versions WHERE doc_id = %s", (doc_id,))["n"] + 1
    else:
        doc_id = str(uuid.uuid4())
        version_no = 1

    staging_uri = storage.uri("staging", f"{version_id}.pdf")
    storage.write_bytes(staging_uri, data)

    vector = llm.embed([probe_text(data)])[0]
    near = _near_duplicates(data, vector, category, doc_id if version_no > 1 else None)
    conflict = {"exact_duplicate": False, "near_duplicates": near, "threshold": get_settings().near_dup_threshold}

    with pool().connection() as conn:
        if version_no == 1:
            conn.execute(
                "INSERT INTO documents VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (doc_id, title, country, business_unit, category, product, access_group, user.username),
            )
        else:
            conn.execute("UPDATE documents SET title = %s WHERE doc_id = %s", (title, doc_id))
        conn.execute(
            """INSERT INTO document_versions (version_id, doc_id, version_no, file_name, file_sha256, staging_uri,
                 effective_date, expiry_date, key_info, probe_embedding, conflict, status, uploaded_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s)""",
            (
                version_id,
                doc_id,
                version_no,
                file_name,
                sha,
                staging_uri,
                effective_date,
                expiry_date,
                jsonb({"country": country, "business_unit": business_unit, "category": category, "product": product}),
                vector,
                jsonb(conflict),
                user.username,
            ),
        )
        conn.execute(
            "INSERT INTO workflow_tasks (task_id, version_id, batch_id, step, role) VALUES (%s, %s, %s, 'VERIFY', 'STEWARD')",
            (str(uuid.uuid4()), version_id, batch_id),
        )
    audit(
        user.username,
        "UPLOAD",
        version_id,
        {"doc_id": doc_id, "version_no": version_no, "file": file_name, "sha256": sha, "batch_id": batch_id,
         "near_duplicates": len([n for n in near if n["flag"] == "near_duplicate"])},
    )
    return {"doc_id": doc_id, "version_id": version_id, "version_no": version_no, "status": "SUBMITTED", "conflict": conflict}


def decide(user: User, task_id: str, decision: str, comment: str | None) -> dict:
    decision = decision.upper()
    if decision not in ("APPROVED", "REJECTED", "RETURNED"):
        raise HTTPException(400, "decision must be APPROVED, REJECTED or RETURNED")
    task = fetch_one(
        """SELECT t.*, v.uploaded_by, v.doc_id FROM workflow_tasks t JOIN document_versions v USING (version_id)
           WHERE t.task_id = %s""",
        (task_id,),
    )
    if not task:
        raise HTTPException(404, "Task not found")
    if task["decision"]:
        raise HTTPException(409, "Task already decided")
    if not user.has_role(task["role"]):
        raise HTTPException(403, f"This step needs the {task['role']} role")
    # Segregation of duties: nobody reviews their own upload, nobody signs two steps.
    if task["uploaded_by"] == user.username:
        audit(user.username, "SOD_VIOLATION_BLOCKED", str(task["version_id"]), {"step": task["step"]})
        raise HTTPException(403, "Segregation of duties: you cannot review your own upload")
    prior = fetch_one(
        "SELECT 1 FROM workflow_tasks WHERE version_id = %s AND assignee = %s AND decision IS NOT NULL",
        (task["version_id"], user.username),
    )
    if prior:
        audit(user.username, "SOD_VIOLATION_BLOCKED", str(task["version_id"]), {"step": task["step"]})
        raise HTTPException(403, "Segregation of duties: you already signed an earlier step for this version")

    vid = str(task["version_id"])
    trigger_pipeline = False
    with pool().connection() as conn:
        conn.execute(
            "UPDATE workflow_tasks SET decision = %s, comment = %s, assignee = %s, decided_at = now() WHERE task_id = %s",
            (decision, comment, user.username, task_id),
        )
        if decision != "APPROVED":
            conn.execute("UPDATE document_versions SET status = %s WHERE version_id = %s", (decision, vid))
        else:
            status, next_step, next_role = NEXT_STEP[task["step"]]
            conn.execute("UPDATE document_versions SET status = %s WHERE version_id = %s", (status, vid))
            if task["step"] == "APPROVE":
                conn.execute("UPDATE document_versions SET approval_id = %s WHERE version_id = %s", (str(uuid.uuid4()), vid))
            if next_step:
                conn.execute(
                    "INSERT INTO workflow_tasks (task_id, version_id, batch_id, step, role) VALUES (%s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), vid, task["batch_id"], next_step, next_role),
                )
            else:
                trigger_pipeline = True
    audit(user.username, task["step"], vid, {"decision": decision, "comment": comment, "task_id": task_id})
    if trigger_pipeline:
        pipeline.submit(vid, user.username)
    return {"task_id": task_id, "decision": decision, "version_id": vid}


def decide_batch(user: User, batch_id: str, decision: str, comment: str | None) -> dict:
    tasks = fetch_all(
        "SELECT task_id, role FROM workflow_tasks WHERE batch_id = %s AND decision IS NULL", (batch_id,)
    )
    mine = [t for t in tasks if user.has_role(t["role"])]
    if not mine:
        raise HTTPException(404, "No pending tasks for you in this batch")
    results = [decide(user, str(t["task_id"]), decision, comment) for t in mine]
    audit(user.username, "BATCH_DECISION", batch_id, {"decision": decision, "count": len(results)})
    return {"batch_id": batch_id, "decided": len(results)}
