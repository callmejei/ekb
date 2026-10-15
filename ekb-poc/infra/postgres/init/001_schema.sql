-- EKB POC system of record. Runs once on first start of the postgres volume.

CREATE TABLE users (                   -- local stand-in for the IdP
  username      TEXT PRIMARY KEY,
  display_name  TEXT NOT NULL,
  roles         TEXT[] NOT NULL,       -- REQUESTOR, STEWARD, OWNER, CUSTODIAN, VIEWER, ADMIN
  access_groups TEXT[] NOT NULL
);

CREATE TABLE documents (
  doc_id        UUID PRIMARY KEY,
  title         TEXT NOT NULL,
  country       TEXT NOT NULL,
  business_unit TEXT NOT NULL,
  category      TEXT NOT NULL,         -- Loans, CFS, Funding, Insurance, Policy
  product       TEXT,
  access_group  TEXT NOT NULL,
  owner_user    TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE document_versions (
  version_id      UUID PRIMARY KEY,
  doc_id          UUID REFERENCES documents(doc_id),
  version_no      INT NOT NULL,
  file_name       TEXT NOT NULL,
  file_sha256     TEXT NOT NULL,
  staging_uri     TEXT NOT NULL,       -- where the file waits while under review
  raw_uri         TEXT,                -- immutable raw-zone copy, set once ACTIVE
  effective_date  DATE NOT NULL,
  expiry_date     DATE,
  key_info        JSONB,
  enrichment      JSONB,               -- LLM summary, key info, sample Q&A, entities
  probe_embedding REAL[],              -- document-level vector for the near-duplicate check
  conflict        JSONB,               -- result of the content conflict check
  status          TEXT NOT NULL,       -- SUBMITTED, VERIFIED, APPROVED, ACKNOWLEDGED, ACTIVE,
                                       -- SUPERSEDED, REJECTED, RETURNED
  pipeline_status TEXT,                -- PENDING, RUNNING, DONE, FAILED
  pipeline_error  TEXT,
  page_count      INT,
  chunk_count     INT,
  is_active       BOOLEAN DEFAULT false,
  approval_id     UUID,
  uploaded_by     TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (doc_id, version_no)
);
CREATE INDEX ON document_versions (file_sha256);

CREATE TABLE workflow_tasks (
  task_id     UUID PRIMARY KEY,
  version_id  UUID REFERENCES document_versions(version_id),
  batch_id    UUID,
  step        TEXT NOT NULL,           -- VERIFY, APPROVE, ACKNOWLEDGE
  role        TEXT NOT NULL,           -- STEWARD, OWNER, CUSTODIAN
  assignee    TEXT,
  decision    TEXT,                    -- APPROVED, REJECTED, RETURNED (NULL = pending)
  comment     TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  decided_at  TIMESTAMPTZ
);
CREATE INDEX ON workflow_tasks (role) WHERE decision IS NULL;

CREATE TABLE audit_log (               -- append-only
  audit_id   BIGSERIAL PRIMARY KEY,
  ts         TIMESTAMPTZ DEFAULT now(),
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,
  object_ref TEXT,
  details    JSONB
);

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

CREATE TABLE extracted_tables (        -- PDF tables (prod: Iceberg via Starburst)
  table_id     UUID PRIMARY KEY,
  version_id   UUID REFERENCES document_versions(version_id),
  page         INT,
  caption      TEXT,
  access_group TEXT NOT NULL,
  rows         JSONB
);

CREATE TABLE feedback (
  feedback_id BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ DEFAULT now(),
  username    TEXT NOT NULL,
  trace_id    TEXT NOT NULL,
  rating      INT NOT NULL,            -- 1 = up, -1 = down
  comment     TEXT
);

-- Seeded users: one per workflow role, plus a branch viewer with narrower access
-- so security trimming can be demonstrated.
INSERT INTO users VALUES
  ('alice', 'Alice Tan',    '{REQUESTOR}',          '{RETAIL_PRODUCTS,RISK_POLICY}'),
  ('bob',   'Bob Lim',      '{STEWARD}',            '{RETAIL_PRODUCTS,RISK_POLICY}'),
  ('carol', 'Carol Ng',     '{OWNER}',              '{RETAIL_PRODUCTS,RISK_POLICY}'),
  ('dave',  'Dave Kumar',   '{CUSTODIAN}',          '{RETAIL_PRODUCTS,RISK_POLICY}'),
  ('erin',  'Erin Wong',    '{VIEWER}',             '{RETAIL_PRODUCTS}'),
  ('admin', 'Platform Admin','{ADMIN}',             '{RETAIL_PRODUCTS,RISK_POLICY}');
