# Enterprise Knowledge Base — Local POC

Governed PDFs → maker-checker approval → extraction, LLM enrichment, chunking → hybrid search
(Elasticsearch) + knowledge graph (Neo4j) → grounded answers that cite document, version and page,
trimmed to the user's access groups.

**UI:** http://localhost:8501 · **API docs:** http://localhost:8000/docs · **Trino UI:** http://localhost:8085 · **Neo4j Browser:** http://localhost:7474
(neo4j / see `.env`) · **MinIO console:** http://localhost:9001 · **Elasticsearch:** http://localhost:9200

## Start (Windows PowerShell; `make <target>` does the same on Linux/macOS)

```powershell
copy .env.example .env           # local-only credentials
.\ekb.ps1 up                     # postgres, minio, elasticsearch, neo4j, ollama (GPU), api, ui
.\ekb.ps1 models                 # qwen2.5:7b + bge-m3 into Ollama (~6 GB, once)
.\ekb.ps1 seed                   # synthetic PDFs → bulk upload → batch approvals → indexed (~5 min)
.\ekb.ps1 test                   # unit tests
.\ekb.ps1 security-test          # restricted user never receives RISK_POLICY content
.\ekb.ps1 reset                  # wipe documents/index/graph/lake (keeps models) and re-seed
```

## What runs where (local → production)

| Layer | Local POC | Production target |
|---|---|---|
| Workflow | Built-in maker-checker state machine in PostgreSQL (`WORKFLOW_ENGINE=builtin`) | Flowable |
| System of record | PostgreSQL 16.4 | Bank PostgreSQL |
| Object storage | MinIO (S3 API) via fsspec — zones `staging/`, `raw/`, `processed/`, `curated/` | S3 / HDFS (change `LAKE_URI`) |
| Extraction | PyMuPDF (text, headings, tables, page numbers); Docling switchable via `EXTRACTOR=docling` | Docling · Tika · PaddleOCR |
| LLM | Ollama 0.6.8, `qwen2.5:7b` (Apache 2.0), OpenAI-compatible API | vLLM (change `LLM_BASE_URL`, `LLM_MODEL`) |
| Embeddings | BGE-M3, 1024-d, normalised | Same |
| Structured serving | Trino 465 → read-only role over curated `kb` views (PostgreSQL connector) | Starburst |
| Hybrid search | Elasticsearch 8.15.3, BM25 + kNN (int8 HNSW), RRF k=60 merged in Python | Bank Elasticsearch (`ES_USE_NATIVE_RRF` if licensed) |
| Knowledge graph | Neo4j 5.26 Community | Neo4j (Enterprise decision after POC) |
| Reranker | Off by default (`RERANK_ENABLED`) — bge-reranker-v2-m3 hook in `retrieval/hybrid.py` | bge-reranker-v2-m3 |
| Identity | Seeded users, `X-User` header | Keycloak / bank IdP |
| UI | React + Vite + Tailwind (Prism design system), served by nginx | Same or LibreChat |

Image versions are pinned in `docker-compose.yml`. Upstream `minio/minio` images were withdrawn from
Docker Hub, so the local stack uses `bitnamilegacy/minio:2025.4.22-debian-12-r1`.

## Switching the LLM (local ⇄ hosted)

The answer/enrichment model is configured in `.env`; embeddings stay on local BGE-M3, so no re-index is needed.

| | `LLM_BASE_URL` | `LLM_MODEL` | `LLM_API_KEY` |
|---|---|---|---|
| Local (spec default, nothing leaves the machine) | `http://ollama:11434/v1` | `qwen2.5:7b` | *(empty)* |
| Hosted comparison (questions + retrieved passages go to OpenAI) | `https://api.openai.com/v1` | `gpt-4.1-mini` | your key |

Apply with `docker compose up -d api`. The model used is shown under every answer and in the audit trail.
Security trimming happens before the LLM is called, so it is unaffected by the choice of model.

## Demo users

| User | Role | Access groups |
|---|---|---|
| alice | Requestor | RETAIL_PRODUCTS, RISK_POLICY |
| bob | Data Steward | RETAIL_PRODUCTS, RISK_POLICY |
| carol | Data Owner | RETAIL_PRODUCTS, RISK_POLICY |
| dave | Data Custodian | RETAIL_PRODUCTS, RISK_POLICY |
| erin | Branch viewer | RETAIL_PRODUCTS only |
| admin | Administrator (audit trail) | both |

Sample content is synthetic ("Sample Bank", fictional regulatory notices). `RISK_POLICY` holds the
Responsible Lending Policy and Retail Loan Pricing Guidelines; everything else is `RETAIL_PRODUCTS`.

## Before the demo

```powershell
.\ekb.ps1 up        # if the laptop was restarted
.\ekb.ps1 warmup    # loads the models onto the GPU; the first answer is otherwise ~20 s
```

To repeat the demo from a clean state (v2 upload, duplicate checks): `.\ekb.ps1 reset` (~6 min).

Known limit of the local 7B model: range arithmetic over tables (e.g. "which band does SGD 1.2M fall in")
can be wrong. `gpt-4.1-mini` answers it correctly; a larger self-hosted model on vLLM would too.

## Demo script (~15 minutes)

1. **Security trimming.** Sign in as **erin** → Ask: *"What discount can a branch manager give on a home loan?"*
   → "could not find this". Switch to **alice** → same question → *up to 0.10%* with a citation to the
   Retail Loan Pricing Guidelines, page 1. Click the citation to open the PDF at that page.
2. **Hybrid vs graph.** As alice, ask *"What rules apply when we lend to a customer for a car loan?"* in
   **Hybrid only** (cites the Car Loan PDS and pricing guidelines), then **Hybrid + graph**: the graph follows
   `GOVERNS` links to the Responsible Lending Policy and the Customer Due Diligence Policy. Open *Show retrieval*
   to see which chunks came from the graph and through which entity.
3. **Maker-checker + versioning.** As **alice** → Upload → *New version of* "Home Loan Product Disclosure
   Sheet" → `data/samples/home_loan_pds_v2.pdf` (effective 1 Oct 2026, lower rates).
   - Try approving as alice: not possible (segregation of duties).
   - **bob** verifies → **carol** approves → **dave** acknowledges. Library → Document register shows the
     pipeline stages live, then v2 ACTIVE and v1 SUPERSEDED.
   - Ask *"What is the year 1 fixed rate for the home loan?"* → **2.15%** cited to **v2** (was 2.45% in v1).
4. **Content conflict check.** As alice, upload `home_loan_pds_v1.pdf` again → **blocked as exact duplicate**.
   Upload `housing_loan_factsheet.pdf` as a new document → bob sees a **near-duplicate** warning in Approvals.
5. **Audit.** Sign in as **admin** → Audit trail: every upload, decision, query and LLM call; the table
   rejects UPDATE/DELETE at the database.
6. **Under the hood (optional).** Neo4j Browser: `MATCH (p:Policy)-[r:GOVERNS]->(x) RETURN p, r, x`.
   MinIO console: `ekb-lake/raw/SG/...` immutable originals, `processed/` Markdown, `curated/` chunks.

## Design notes and deliberate deviations from the build spec

- **Staging zone.** Files under review live in `staging/`; only acknowledged versions are landed in `raw/`.
- **Near-duplicate check** uses a document-level BGE-M3 probe embedding computed at upload (chunks do not
  exist yet at Verify). New versions of the same document are excluded from the comparison.
- **Graph security.** Shared entity nodes (Product, Policy, Regulation) carry no access group; every
  `MENTIONS`, `GOVERNS`, `REQUIRES` edge and every Chunk carries `doc_id`, `version_id`, `access_group`,
  `is_active`, and traversal filters on them inside Cypher. Entities are kept only if the document text
  actually names them, and entity-name hints given to the LLM are limited to the same access group, so a
  restricted name cannot leak into a public document's graph.
- **Graph facts in answers.** Relationships found during expansion are passed to the LLM with a cited
  evidence chunk, fetched under the same mandatory filter.
- **Not in this build:** Flowable/Airflow/Langfuse/Keycloak profiles, Ragas evaluation, OCR.

## Data route (text-to-SQL, ported from Prism Sage)

Every question is routed by the LLM to **document** (hybrid search + graph), **data** (SQL through Trino)
or **mixed** (both in parallel, one answer citing `[n]` documents and `[SQL]`). The Ask page also lets you
force a route.

| View (`postgresql.kb.*`) | Contents |
|---|---|
| `documents` | Document register — every version, status, dates, owner |
| `table_rows`, `table_cells` | Tables extracted from the PDFs (cells with parsed `cell_number`) |
| `approvals` | Maker-checker history |
| `product_monthly` | Synthetic data mart — accounts, balances, arrears by product and month |
| `credit_exceptions` | Synthetic restricted mart (`RISK_POLICY`) — lending-policy exceptions |

Pipeline (`retrieval/data.py`, `retrieval/sql_guard.py`): schema context + live sample values → strict-JSON
SQL with the question fenced as untrusted input → **guard**: one read-only SELECT, allow-listed views only,
every view rewritten to a CTE with `access_group IN (<user's groups>)`, LIMIT 500 → Trino (as the end user)
→ one retry with the engine error → answer written only from the rows. Trino itself connects as
`ekb_reader`, which can read only the `kb` views. Every execution, error and block is audited.

Try: *"Which products have a late payment charge above SGD 90?"*, *"Show the monthly arrears rate trend for
personal loans"*, *"How many lending policy exceptions were approved per product in 2026?"* (alice gets
numbers, erin gets none), *"What is the latest arrears rate on credit cards, and what is the late payment fee?"* (mixed).
