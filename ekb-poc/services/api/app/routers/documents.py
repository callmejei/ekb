import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import fitz
from fastapi.responses import Response

from .. import storage, workflow
from ..audit import audit
from ..db import fetch_all, fetch_one
from ..pipeline import run as pipeline
from ..security import User, current_user

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    country: str = Form("SG"),
    business_unit: str = Form(...),
    category: str = Form(...),
    product: str | None = Form(None),
    access_group: str = Form(...),
    effective_date: date = Form(...),
    expiry_date: date | None = Form(None),
    doc_id: str | None = Form(None),
    user: User = Depends(current_user),
):
    data = await file.read()
    return workflow.upload(
        user,
        data=data,
        file_name=file.filename or "upload.pdf",
        title=title,
        country=country,
        business_unit=business_unit,
        category=category,
        product=product or None,
        access_group=access_group,
        effective_date=effective_date,
        expiry_date=expiry_date,
        doc_id=doc_id or None,
    )


@router.post("/bulk")
async def bulk_upload(
    files: list[UploadFile] = File(...),
    manifest: str = Form(..., description="JSON list of metadata objects, one per file, matched by file_name"),
    user: User = Depends(current_user),
):
    entries = {m["file_name"]: m for m in json.loads(manifest)}
    batch_id = str(uuid.uuid4())
    results = []
    for f in files:
        m = entries.get(f.filename or "")
        if not m:
            results.append({"file_name": f.filename, "error": "not in manifest"})
            continue
        try:
            r = workflow.upload(
                user,
                data=await f.read(),
                file_name=f.filename or "",
                title=m["title"],
                country=m.get("country", "SG"),
                business_unit=m["business_unit"],
                category=m["category"],
                product=m.get("product"),
                access_group=m["access_group"],
                effective_date=date.fromisoformat(m["effective_date"]),
                expiry_date=date.fromisoformat(m["expiry_date"]) if m.get("expiry_date") else None,
                batch_id=batch_id,
            )
            results.append({"file_name": f.filename, **r})
        except HTTPException as e:
            results.append({"file_name": f.filename, "error": e.detail})
    audit(user.username, "BULK_UPLOAD", batch_id, {"files": len(files)})
    return {"batch_id": batch_id, "results": results}


@router.get("")
def list_documents(user: User = Depends(current_user)):
    """Every document in the user's access groups, with all its versions and their workflow state."""
    rows = fetch_all(
        """SELECT d.doc_id, d.title, d.country, d.business_unit, d.category, d.product, d.access_group,
                  d.owner_user, v.version_id, v.version_no, v.status, v.is_active, v.effective_date,
                  v.expiry_date, v.pipeline_status, v.pipeline_error, v.page_count, v.chunk_count,
                  v.uploaded_by, v.created_at, v.file_name,
                  v.enrichment->>'summary' AS summary
           FROM documents d JOIN document_versions v USING (doc_id)
           WHERE d.access_group = ANY(%s)
           ORDER BY d.title, v.version_no DESC""",
        (list(user.access_groups),),
    )
    docs: dict[str, dict] = {}
    for r in rows:
        d = docs.setdefault(
            str(r["doc_id"]),
            {k: r[k] for k in ("doc_id", "title", "country", "business_unit", "category", "product", "access_group", "owner_user")}
            | {"versions": []},
        )
        d["versions"].append(
            {k: r[k] for k in ("version_id", "version_no", "status", "is_active", "effective_date", "expiry_date",
                               "pipeline_status", "pipeline_error", "page_count", "chunk_count", "uploaded_by",
                               "created_at", "file_name", "summary")}
        )
    return list(docs.values())


def _visible_version(version_id: str, user: User) -> dict:
    v = fetch_one(
        """SELECT v.*, d.title, d.country, d.business_unit, d.category, d.product, d.access_group, d.owner_user
           FROM document_versions v JOIN documents d USING (doc_id) WHERE v.version_id = %s""",
        (version_id,),
    )
    if not v or v["access_group"] not in user.access_groups:
        raise HTTPException(404, "Document not found")
    return v


@router.get("/{version_id}")
def document_detail(version_id: str, user: User = Depends(current_user)):
    v = _visible_version(version_id, user)
    v.pop("probe_embedding", None)
    tasks = fetch_all(
        "SELECT step, role, assignee, decision, comment, created_at, decided_at FROM workflow_tasks "
        "WHERE version_id = %s ORDER BY created_at",
        (version_id,),
    )
    tables = fetch_all(
        "SELECT page, caption, rows FROM extracted_tables WHERE version_id = %s ORDER BY page", (version_id,)
    )
    return {"version": v, "tasks": tasks, "tables": tables}


@router.get("/{version_id}/file")
def document_file(version_id: str, user: User = Depends(current_user)):
    v = _visible_version(version_id, user)
    data = storage.read_bytes(v["raw_uri"] or v["staging_uri"])
    audit(user.username, "VIEW_FILE", version_id)
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{v["file_name"]}"'},
    )


@router.get("/{version_id}/pages")
def page_count(version_id: str, user: User = Depends(current_user)):
    v = _visible_version(version_id, user)
    doc = fitz.open(stream=storage.read_bytes(v["raw_uri"] or v["staging_uri"]), filetype="pdf")
    return {"page_count": doc.page_count}


@router.get("/{version_id}/pages/{page}")
def page_image(version_id: str, page: int, user: User = Depends(current_user)):
    """Server-rendered page preview, so review works in any browser (no PDF plug-in needed)."""
    v = _visible_version(version_id, user)
    doc = fitz.open(stream=storage.read_bytes(v["raw_uri"] or v["staging_uri"]), filetype="pdf")
    if not 1 <= page <= doc.page_count:
        raise HTTPException(404, "No such page")
    png = doc[page - 1].get_pixmap(dpi=110).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.post("/{version_id}/reindex")
def reindex(version_id: str, user: User = Depends(current_user)):
    if not user.has_role("CUSTODIAN"):
        raise HTTPException(403, "Custodian or admin only")
    v = _visible_version(version_id, user)
    if v["status"] not in ("ACKNOWLEDGED", "ACTIVE"):
        raise HTTPException(409, "Only acknowledged versions can be indexed")
    pipeline.submit(version_id, user.username)
    audit(user.username, "REINDEX", version_id)
    return {"version_id": version_id, "pipeline_status": "PENDING"}
