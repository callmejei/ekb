"""Initial bulk load through the real API and maker-checker workflow.

Alice (Requestor) bulk-uploads the seed documents as one batch; Bob, Carol and Dave approve the
batch manifest at each step; the pipeline indexes everything. Run inside the api container:
    python -m app.seed
"""

import json
import time
from pathlib import Path

import httpx

from .samples import SAMPLES, main as render_samples

API = "http://localhost:8000/api"
SAMPLE_DIR = Path("/samples")


def call(method: str, path: str, user: str, **kw) -> dict:
    r = httpx.request(method, API + path, headers={"X-User": user}, timeout=600, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} as {user}: {r.status_code} {r.text}")
    return r.json()


def main() -> None:
    render_samples(str(SAMPLE_DIR))
    seed = [(f, m) for f, _, m, load in SAMPLES if load]
    manifest = [{"file_name": f, "country": "SG", **m, "product": m["product"] or None} for f, m in seed]
    files = [("files", (f, (SAMPLE_DIR / f).read_bytes(), "application/pdf")) for f, _ in seed]
    res = call("POST", "/documents/bulk", "alice", files=files, data={"manifest": json.dumps(manifest)})
    batch = res["batch_id"]
    for r in res["results"]:
        print("uploaded", r.get("file_name"), r.get("status") or r.get("error"))

    for user in ("bob", "carol", "dave"):
        out = call("POST", f"/tasks/batch/{batch}/decision", user, json={"decision": "APPROVED", "comment": "Initial load batch manifest approved"})
        print(user, "approved batch:", out["decided"], "tasks")

    print("waiting for the pipeline to index the batch ...")
    while True:
        docs = call("GET", "/documents", "admin")
        states = [v["pipeline_status"] for d in docs for v in d["versions"]]
        done = sum(s in ("DONE", "FAILED") for s in states)
        print(f"  {done}/{len(states)} processed", flush=True)
        if done == len(states):
            break
        time.sleep(10)
    for d in docs:
        for v in d["versions"]:
            print(f"  {d['title']:55} v{v['version_no']} {v['status']:10} chunks={v['chunk_count']} {v['pipeline_error'] or ''}")


if __name__ == "__main__":
    main()
