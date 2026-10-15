# Enterprise Knowledge Base — Local POC Build Spec

> **For the AI coding assistant:** This file is the single source of truth for the build.
> Work **one milestone at a time** (Section 17). After each milestone, stop, run its
> acceptance checks, and report results before continuing. Do not skip tests, do not
> add components not listed here, and ask before changing any design decision.

---

## 1. Goal

Build a local, Docker-based proof of concept of an enterprise knowledge base that:

1. Ingests PDF documents through a governed **maker-checker** workflow.
2. Extracts, enriches, chunks and indexes them.
3. Answers natural-language questions using **hybrid search (Elasticsearch)** plus a
   **knowledge graph (Neo4j)**, and structured data via **SQL federation (Trino)**.
4. Enforces **access-group security trimming** on every retrieval.
5. Cites document, version and page for every answer.
6. Measures answer quality against a question benchmark.

**POC scope:** PDFs only, around 100 documents locally (scale target 1,000), 1–2 categories.

---

## 2. Ground rules (must follow)

- **Open source only.** No paid SaaS, no external LLM APIs. All models run locally.
- **No confidential data on the local machine.** Use public or synthetic PDFs
  (for example, published product disclosure sheets, public policy documents) unless
  the use of internal documents has been formally approved.
- **Config-driven swaps.** Every external dependency (LLM endpoint, object store,
  SQL engine, graph store) is reached through an interface and configured in `.env`,
  so local components can be replaced by production ones without code changes.
- **Security trimming is mandatory.** No query to Elasticsearch, Neo4j or Trino may run
  without the caller's access groups applied. Users never query stores directly.
- **Lineage is mandatory.** Every chunk and graph node stores `doc_id`, `version_id`,
  `page` and `approval_id`.
- **Only active, in-date versions are retrievable.**
- **Audit everything.** Every workflow action and every LLM call writes an audit record.
- Python 3.11+, type hints, `ruff` + `black`, `pytest`. Small, testable modules.

---

## 3. Local vs production mapping

| Layer | Local POC (this build) | Production target |
|---|---|---|
| Workflow | Flowable REST (Docker) | Flowable |
| System of record | PostgreSQL 16 | Bank PostgreSQL |
| Object storage | Local volume via `fsspec` (`file://`) | S3 / HDFS (`s3://`, `hdfs://`) |
| Orchestration | Python CLI pipeline; Airflow optional profile | Apache Airflow |
| Extraction | Docling, Apache Tika, PaddleOCR (optional) | Same |
| LLM serving | Ollama (OpenAI-compatible API) | vLLM (OpenAI-compatible API) |
| Embeddings | BGE-M3 | BGE-M3 |
| Reranker | bge-reranker-v2-m3 | Same |
| Hybrid search | Elasticsearch 8.x single node | Bank Elasticsearch |
| Knowledge graph | Neo4j 5 Community | Neo4j (Enterprise decision after POC) |
| Structured serving | Trino (open-source engine behind Starburst) | Starburst |
| PDF tables | PostgreSQL tables (via Trino PostgreSQL connector) | Apache Iceberg via Starburst |
| Agent framework | LlamaIndex | Haystack or LlamaIndex |
| Tracing | Langfuse (optional profile) | Langfuse |
| Evaluation | Ragas | Ragas |
| Identity | Static users in config; Keycloak optional profile | Keycloak / bank IdP |
| UI | Thin web UI (FastAPI + simple HTML/JS or Streamlit) | Thin UI or LibreChat |

Because Ollama and vLLM both expose an OpenAI-compatible API, switching is a change to
`LLM_BASE_URL` and `LLM_MODEL` only.

---

## 4. Machine prerequisites

- Docker Desktop (or Docker Engine + Compose v2).
- **RAM: 32 GB recommended** (16 GB minimum with optional profiles off).
- **Disk: 40 GB free.**
- GPU optional. Without a GPU, use a small model (for example a 3B–8B instruct model)
  and expect slower enrichment.
- Docker memory allocation: at least 12 GB for the core profile.

---

## 5. Repository structure

```
ekb-poc/
├── docker-compose.yml
├── .env.example
├── Makefile
├── README.md
├── infra/
│   ├── postgres/init/001_schema.sql
│   ├── elasticsearch/ekb_chunks_mapping.json
│   ├── neo4j/constraints.cypher
│   ├── trino/catalog/postgresql.properties
│   └── flowable/maker_checker.bpmn20.xml
├── services/
│   ├── api/                  # FastAPI: intake, workflow, query, admin
│   │   ├── main.py
│   │   ├── routers/{documents,workflow,query,admin}.py
│   │   ├── security.py       # user → access groups, filter builders
│   │   └── audit.py
│   ├── pipeline/             # extraction → enrichment → chunking → indexing
│   │   ├── cli.py
│   │   ├── extract.py
│   │   ├── enrich.py
│   │   ├── chunk.py
│   │   ├── index_es.py
│   │   └── index_graph.py
│   ├── retrieval/            # hybrid search, graph expansion, rerank, routing
│   │   ├── hybrid.py
│   │   ├── graph.py
│   │   ├── rerank.py
│   │   ├── router.py
│   │   └── answer.py
│   ├── common/               # config, storage, llm client, db clients, models
│   └── ui/                   # thin chat + browse UI
├── eval/
│   ├── benchmark.csv         # question, expected_answer, question_type, access_group
│   └── run_eval.py
├── data/
│   ├── inbox/                # PDFs to upload (public/synthetic only)
│   └── lake/{raw,processed,curated}/
└── tests/
```

---

## 6. Docker Compose

Use **profiles** so the core stack runs on a laptop and heavier services are opt-in.

| Service | Image (pin exact version) | Profile | Port |
|---|---|---|---|
| postgres | `postgres:16` | core | 5432 |
| elasticsearch | `docker.elastic.co/elasticsearch/elasticsearch:8.x` | core | 9200 |
| neo4j | `neo4j:5-community` | core | 7474, 7687 |
| trino | `trinodb/trino` | core | 8080 |
| ollama | `ollama/ollama` | core | 11434 |
| tika | `apache/tika` | core | 9998 |
| api | build `services/api` | core | 8000 |
| ui | build `services/ui` | core | 8501 |
| flowable | `flowable/flowable-rest` | workflow | 8090 |
| airflow | `apache/airflow` (standalone) | orchestration | 8081 |
| langfuse | `langfuse/langfuse` (+ its dependencies) | observability | 3000 |
| keycloak | `quay.io/keycloak/keycloak` | auth | 8180 |

Requirements:

- Pin every image to an exact version tag, never `latest`. Pick versions at least two
  weeks old and record them in `README.md`.
- Elasticsearch: `discovery.type=single-node`, `ES_JAVA_OPTS=-Xms2g -Xmx2g`.
  Security may be disabled **locally only**, behind a clear `# LOCAL ONLY` comment.
- Neo4j: heap 2 GB, page cache 1 GB, password from `.env`.
- Health checks on every service; `api` waits for postgres, elasticsearch, neo4j, ollama.
- Named volumes for all data so `docker compose down` keeps data; `make reset` wipes it.

Makefile targets: `up`, `up-all`, `down`, `reset`, `logs`, `models` (pull Ollama models),
`ingest`, `index`, `eval`, `test`.

---

## 7. Configuration (`.env.example`)

```
# Storage
LAKE_URI=file:///data/lake            # prod: s3://bucket/ekb or hdfs://...

# PostgreSQL
PG_HOST=postgres
PG_DB=ekb
PG_USER=ekb
PG_PASSWORD=change_me

# Elasticsearch
ES_URL=http://elasticsearch:9200
ES_INDEX_ALIAS=ekb-chunks
ES_USE_NATIVE_RRF=false               # true only if licence tier supports it

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me

# Trino (Starburst in prod)
SQL_ENGINE_URL=http://trino:8080
SQL_CATALOG=postgresql

# LLM (Ollama local, vLLM prod — both OpenAI-compatible)
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=<small-apache-2.0-instruct-model>
EMBED_MODEL=bge-m3
EMBED_DIM=1024
RERANK_MODEL=BAAI/bge-reranker-v2-m3

# Workflow
WORKFLOW_ENGINE=flowable              # or "builtin" if workflow profile is off
FLOWABLE_URL=http://flowable:8080/flowable-rest

# Observability (optional)
LANGFUSE_ENABLED=false
```

If the `workflow` profile is off, implement a **built-in state machine** in PostgreSQL
with the same states and transitions, selected by `WORKFLOW_ENGINE=builtin`.

---

## 8. Data model (PostgreSQL)

```sql
CREATE TABLE documents (
  doc_id        UUID PRIMARY KEY,
  title         TEXT NOT NULL,
  country       TEXT NOT NULL,
  business_unit TEXT NOT NULL,
  category      TEXT NOT NULL,        -- e.g. Loans, CFS, Funding, Insurance
  product       TEXT,
  access_group  TEXT NOT NULL,
  owner_user    TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE document_versions (
  version_id     UUID PRIMARY KEY,
  doc_id         UUID REFERENCES documents(doc_id),
  version_no     INT NOT NULL,
  file_sha256    TEXT NOT NULL,
  raw_uri        TEXT NOT NULL,
  effective_date DATE NOT NULL,
  expiry_date    DATE,
  key_info       JSONB,
  status         TEXT NOT NULL,       -- DRAFT, SUBMITTED, VERIFIED, APPROVED,
                                      -- ACKNOWLEDGED, ACTIVE, SUPERSEDED, REJECTED
  is_active      BOOLEAN DEFAULT false,
  approval_id    UUID,
  created_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (doc_id, version_no)
);

CREATE TABLE workflow_tasks (
  task_id      UUID PRIMARY KEY,
  version_id   UUID REFERENCES document_versions(version_id),
  batch_id     UUID,                  -- for batch approval of bulk loads
  step         TEXT NOT NULL,         -- UPLOAD, VERIFY, APPROVE, ACKNOWLEDGE
  role         TEXT NOT NULL,         -- REQUESTOR, STEWARD, OWNER, CUSTODIAN
  assignee     TEXT,
  decision     TEXT,                  -- APPROVED, REJECTED, RETURNED
  comment      TEXT,
  decided_at   TIMESTAMPTZ
);

CREATE TABLE audit_log (               -- append-only
  audit_id   BIGSERIAL PRIMARY KEY,
  ts         TIMESTAMPTZ DEFAULT now(),
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,           -- UPLOAD, VERIFY, APPROVE, QUERY, LLM_CALL, ...
  object_ref TEXT,
  details    JSONB
);
-- Revoke UPDATE and DELETE on audit_log from the application role.

CREATE TABLE extracted_tables (        -- PDF tables, queried through Trino
  table_id    UUID PRIMARY KEY,
  version_id  UUID REFERENCES document_versions(version_id),
  page        INT,
  caption     TEXT,
  access_group TEXT NOT NULL,
  rows        JSONB                   -- prod: written as Iceberg tables instead
);

CREATE TABLE users (                   -- local stand-in for IdP
  username      TEXT PRIMARY KEY,
  roles         TEXT[] NOT NULL,
  access_groups TEXT[] NOT NULL
);
```

Seed 4 users: one per role, with different access groups, so security trimming can be tested.

---

## 9. Maker-checker workflow

States: `DRAFT → SUBMITTED → VERIFIED → APPROVED → ACKNOWLEDGED → ACTIVE`,
with `REJECTED` and `RETURNED` from any review step.

| Step | Role | Action |
|---|---|---|
| Upload | Requestor | Uploads PDF + metadata, submits |
| Verify | Data Steward | Checks content and metadata |
| Approve | Data Owner | Approves for use |
| Acknowledge | Custodian | Takes custody; version becomes ACTIVE |

Rules:

- A user cannot verify or approve their own upload (**segregation of duties**).
- Routing mode configurable: `sequential` (default) or `parallel` for Verify + Approve.
- **Batch approval:** bulk loads create one `batch_id`; reviewers approve the batch manifest.
- When a new version becomes ACTIVE, the previous version becomes SUPERSEDED,
  `is_active=false`, and is removed from search (Section 11).
- **Content conflict check** runs at Verify:
  - exact duplicate: same `file_sha256` already exists → block;
  - near-duplicate: top chunk cosine similarity > 0.95 against active documents in the
    same category → flag to the steward with the matching document.
- Every transition writes to `audit_log`.

---

## 10. Pipeline

Triggered when a version becomes ACTIVE (or via `make ingest` / `make index` for bulk).
Each stage is idempotent and keyed by `version_id`.

1. **Land:** copy original to `raw/{country}/{bu}/{category}/{doc_id}/{version_id}.pdf`;
   store SHA-256.
2. **Extract:** Docling converts PDF to Markdown with page numbers and table structures.
   Tika is the fallback for non-PDF files. OCR (PaddleOCR) only when a page has no text
   layer. Write `processed/{version_id}/document.md` and `tables.json`.
3. **Tables:** write each extracted table to `extracted_tables` with page and access group.
4. **Enrich (LLM):** per document, generate JSON with `summary`, `key_info`,
   `sample_qa` (5 pairs) and `entities` (types in Section 12). Validate against a
   Pydantic schema; retry once on invalid JSON. Log each call to `audit_log`.
5. **Chunk:** split by heading; target 400–800 tokens with 15% overlap; never split a
   table; prefix each chunk with its heading path for context.
6. **Embed:** BGE-M3, 1024 dimensions, normalised.
7. **Index:** bulk-index chunks to Elasticsearch (Section 11) and entities to Neo4j
   (Section 12). Write `curated/{version_id}/chunks.jsonl` as the record of what was indexed.
8. **Deactivate superseded versions:** set `is_active=false` in Elasticsearch and Neo4j.

---

## 11. Elasticsearch

Index `ekb-chunks-v1`, alias `ekb-chunks`.

```json
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": {
    "properties": {
      "chunk_id":     { "type": "keyword" },
      "doc_id":       { "type": "keyword" },
      "version_id":   { "type": "keyword" },
      "approval_id":  { "type": "keyword" },
      "title":        { "type": "text" },
      "heading_path": { "type": "text" },
      "chunk_text":   { "type": "text" },
      "embedding":    { "type": "dense_vector", "dims": 1024, "index": true,
                        "similarity": "cosine",
                        "index_options": { "type": "int8_hnsw" } },
      "page":         { "type": "integer" },
      "is_active":    { "type": "boolean" },
      "country":      { "type": "keyword" },
      "business_unit":{ "type": "keyword" },
      "category":     { "type": "keyword" },
      "product":      { "type": "keyword" },
      "effective_date": { "type": "date" },
      "expiry_date":  { "type": "date" },
      "access_group": { "type": "keyword" }
    }
  }
}
```

**Mandatory filter** (built in `security.py`, applied to every query):

```
is_active = true
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
AND access_group IN user.access_groups
```

**Hybrid query:**

- BM25 `multi_match` on `chunk_text`, `heading_path`, `title` with the mandatory filter.
- kNN on `embedding`, `k=50`, `num_candidates=200`, with the mandatory filter **inside**
  the kNN `filter` clause (never post-filter).
- Merge with RRF (k=60). If `ES_USE_NATIVE_RRF=false`, merge in Python.
- Rerank top 50 with bge-reranker-v2-m3; keep top 8.

---

## 12. Neo4j graph

Node labels: `Document`, `Product`, `Policy`, `Regulation`, `BusinessUnit`, `Chunk`.

Relationships:

```
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONS]->(:Product|Policy|Regulation)
(:Policy)-[:GOVERNS]->(:Product)
(:Regulation)-[:REQUIRES]->(:Policy)
(:Document)-[:OWNED_BY]->(:BusinessUnit)
(:Document)-[:SUPERSEDES]->(:Document)
```

Every node and relationship carries `doc_id`, `version_id`, `access_group`, `is_active`.

`constraints.cypher`: unique constraints on `chunk_id`, `doc_id`, and on entity
`name + type`. Entity names are normalised (case, whitespace) before merge.

**Graph expansion at query time:** take `chunk_id`s from the top hybrid results →
1–2 hop traversal to related entities and their other chunks → filter every node and
relationship by `is_active` and the user's access groups **inside the Cypher query** →
return up to 5 extra chunks as additional context.

Neo4j Community has no role-based access control, so the API is the only client.

---

## 13. Retrieval and agent service (FastAPI)

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents` | Upload PDF + metadata (Requestor) |
| POST | `/documents/bulk` | Bulk upload with batch manifest |
| GET | `/tasks` | Pending tasks for current user |
| POST | `/tasks/{id}/decision` | Approve / reject / return |
| POST | `/query` | Ask a question |
| GET | `/browse` | Faceted browse (category, product, BU) |
| POST | `/feedback` | Thumbs up/down on an answer |
| GET | `/audit` | Audit log (admin only) |

Local auth: header `X-User: <username>` resolved against the `users` table.
Keep this behind an interface so Keycloak (OIDC) can replace it.

**Router** (`router.py`) classifies each question with the LLM into one of:

| Type | Path |
|---|---|
| `document` | Hybrid search + graph expansion + rerank → answer |
| `data` | Text-to-SQL through Trino → answer from result rows |
| `mixed` | Both paths, answers combined |

**Text-to-SQL rules:**

- Allow-list of schemas and tables; read-only SQL user; `SELECT` only.
- Reject any statement containing DDL or DML; enforce `LIMIT 500`.
- Apply the access-group filter on `extracted_tables` and any other table with an
  `access_group` column.
- Return the SQL used alongside the answer.

**Answer generation:**

- System prompt: answer **only** from the provided context; if the context is
  insufficient, say so; never use outside knowledge.
- Every claim cites `[doc title, version, page]`.
- Response JSON: `answer`, `citations[]`, `route`, `sql` (if any), `trace_id`.
- Log question, route, retrieved chunk ids, model, latency and user to `audit_log`
  (and Langfuse if enabled).

---

## 14. Trino (local stand-in for Starburst)

- Catalog `postgresql` pointing at the `ekb` database, read-only user.
- Expose `documents`, `document_versions` (metadata only) and `extracted_tables`.
- Keep SQL ANSI-compatible so it runs unchanged on Starburst.

---

## 15. UI

Thin web UI with:

- **Login** as one of the seeded users (dropdown, local only).
- **Upload** page: PDF + metadata form.
- **Tasks** page: pending approvals with document preview and conflict-check warnings.
- **Ask** page: chat, answers with clickable citations, route shown, thumbs up/down.
- **Browse** page: facets by category, product, business unit.

---

## 16. Evaluation

`eval/benchmark.csv` columns: `question, expected_answer, question_type
(single_topic|cross_topic|data), access_group`.

`run_eval.py`:

- Runs every question as a user in the matching access group.
- Runs two configurations: **hybrid only** and **hybrid + graph**.
- Ragas metrics: faithfulness, answer relevancy, context precision, context recall.
- **Security test:** re-run a subset as a user **without** the access group; any answer
  containing restricted content is a failure.
- Outputs `eval/report.md` with scores by configuration and question type.

---

## 17. Milestones and acceptance criteria

Build in this order. Stop after each milestone and report.

**M1 — Infrastructure**
- `make up` starts the core profile; all health checks pass.
- Schema, ES index, Neo4j constraints and Trino catalog created automatically.
- Ollama models pulled with `make models`.

**M2 — Intake and workflow**
- Upload → Verify → Approve → Acknowledge works end to end in the UI and API.
- Segregation of duties enforced; batch approval works.
- Duplicate upload is blocked; audit log records every step.

**M3 — Extraction and enrichment**
- 10 sample PDFs produce Markdown with page numbers and extracted tables.
- Enrichment JSON validates against the schema for all 10.

**M4 — Indexing**
- Chunks searchable in Elasticsearch; entities visible in Neo4j Browser.
- A new version supersedes the old one, and the old one disappears from search.

**M5 — Query**
- Document questions return answers with correct citations.
- Data questions return answers with the SQL shown.
- A user without the access group gets no restricted content (automated test).

**M6 — Evaluation**
- `make eval` produces `report.md` comparing hybrid-only against hybrid + graph.

**M7 — Hardening**
- README with setup, versions, and how each local component maps to production.
- Unit tests for security filters, chunking, router and SQL guard.
- Optional profiles (Flowable, Airflow, Langfuse, Keycloak) start and integrate.

---

## 18. Engineering standards

- Configuration only through environment variables; no secrets in code or Git.
- Structured JSON logging with `trace_id` on every request.
- Retry with backoff for LLM and store calls; timeouts on every network call.
- All store access through repository classes in `services/common`, so production
  clients can be swapped in.
- Tests that need services use the running Docker stack; pure logic tests run without it.

---

## 19. Known local limitations

- Single-node Elasticsearch and Neo4j Community: no HA, no clustering.
- Ollama with a small model: lower answer quality and slower enrichment than production vLLM.
- Trino stands in for Starburst; Starburst-specific governance features are not available.
- PDF tables live in PostgreSQL instead of Iceberg.
- Local auth is a header stand-in; not secure, for development only.
