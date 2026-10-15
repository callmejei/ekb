-- Queryable layer for the data route (text-to-SQL through Trino; Starburst in production).
--
-- Trino connects as ekb_reader, which can read ONLY the curated views in schema `kb` — never the
-- base tables. Access groups are still enforced per user by the API, which wraps every view
-- reference in an access_group filter before the SQL reaches Trino.

CREATE SCHEMA IF NOT EXISTS kb;
CREATE SCHEMA IF NOT EXISTS mart;

-- Document register: one row per document version.
CREATE OR REPLACE VIEW kb.documents AS
SELECT v.version_id::text        AS version_id,
       d.doc_id::text            AS doc_id,
       d.title,
       v.version_no,
       v.status,
       v.is_active,
       d.country,
       d.business_unit,
       d.category,
       NULLIF(d.product, '')     AS product,
       d.access_group,
       v.effective_date,
       v.expiry_date,
       v.uploaded_by,
       v.created_at::timestamp(0) AS uploaded_at,
       v.page_count,
       v.chunk_count
FROM documents d JOIN document_versions v USING (doc_id);

-- Tables extracted from PDFs: one row per table row, all cells as "Column: value | ...".
CREATE OR REPLACE VIEW kb.table_rows AS
SELECT t.table_id::text   AS table_id,
       t.version_id::text AS version_id,
       d.title            AS document_title,
       NULLIF(d.product, '') AS product,
       d.category,
       v.version_no,
       v.is_active,
       t.page,
       t.caption          AS table_caption,
       r.ord::int         AS row_no,
       (SELECT string_agg(e.key || ': ' || e.value, ' | ') FROM jsonb_each_text(r.val) e) AS row_text,
       t.access_group
FROM extracted_tables t
JOIN document_versions v USING (version_id)
JOIN documents d USING (doc_id)
CROSS JOIN LATERAL jsonb_array_elements(t.rows) WITH ORDINALITY AS r(val, ord);

-- The same tables, one row per cell, with the first number in the cell parsed out.
CREATE OR REPLACE VIEW kb.table_cells AS
SELECT t.table_id::text   AS table_id,
       t.version_id::text AS version_id,
       d.title            AS document_title,
       NULLIF(d.product, '') AS product,
       d.category,
       v.version_no,
       v.is_active,
       t.page,
       t.caption          AS table_caption,
       r.ord::int         AS row_no,
       e.key              AS column_name,
       e.value            AS cell_value,
       (substring(replace(e.value, ',', '') FROM '-?[0-9]+(?:\.[0-9]+)?'))::double precision AS cell_number,
       t.access_group
FROM extracted_tables t
JOIN document_versions v USING (version_id)
JOIN documents d USING (doc_id)
CROSS JOIN LATERAL jsonb_array_elements(t.rows) WITH ORDINALITY AS r(val, ord)
CROSS JOIN LATERAL jsonb_each_text(r.val) AS e;

-- Maker-checker history.
CREATE OR REPLACE VIEW kb.approvals AS
SELECT w.version_id::text AS version_id,
       d.title            AS document_title,
       v.version_no,
       w.step,
       w.role,
       w.assignee,
       w.decision,
       w.comment,
       w.created_at::timestamp(0) AS created_at,
       w.decided_at::timestamp(0) AS decided_at,
       d.access_group
FROM workflow_tasks w
JOIN document_versions v USING (version_id)
JOIN documents d USING (doc_id);

-- Synthetic data mart (stand-in for the bank's existing marts): monthly product metrics.
CREATE TABLE IF NOT EXISTS mart.product_monthly (
  month                      DATE NOT NULL,
  product                    TEXT NOT NULL,
  active_accounts            INT NOT NULL,
  new_accounts               INT NOT NULL,
  outstanding_balance_sgd_mn NUMERIC(12, 2) NOT NULL,
  arrears_rate_pct           NUMERIC(5, 2) NOT NULL,
  access_group               TEXT NOT NULL,
  PRIMARY KEY (month, product)
);

INSERT INTO mart.product_monthly
SELECT m::date,
       p.product,
       (p.base_accounts * (1 + 0.012 * i))::int,
       (p.base_new * (1 + 0.15 * sin(i)))::int,
       round((p.base_balance * (1 + 0.01 * i))::numeric, 2),
       round((p.base_arrears + 0.08 * cos(i * 0.9))::numeric, 2),
       'RETAIL_PRODUCTS'
FROM generate_series(DATE '2025-10-01', DATE '2026-09-01', INTERVAL '1 month') WITH ORDINALITY AS g(m, i)
CROSS JOIN (VALUES
  ('Home Loan',                 182000, 2100, 61250.00, 0.42),
  ('Car Loan',                   64000, 1450,  3820.00, 0.95),
  ('Personal Loan',              91000, 3900,  1240.00, 2.10),
  ('Credit Card',               845000, 9800,  2960.00, 1.65),
  ('Fixed Deposit',             410000, 7600, 38400.00, 0.00),
  ('Home Protection Insurance', 158000, 1900,     0.00, 0.00)
) AS p(product, base_accounts, base_new, base_balance, base_arrears)
ON CONFLICT DO NOTHING;

-- Restricted mart: lending-policy exceptions by month (RISK_POLICY only).
CREATE TABLE IF NOT EXISTS mart.credit_exceptions (
  month          DATE NOT NULL,
  product        TEXT NOT NULL,
  exceptions     INT NOT NULL,
  approved_by    TEXT NOT NULL,
  access_group   TEXT NOT NULL,
  PRIMARY KEY (month, product, approved_by)
);

INSERT INTO mart.credit_exceptions
SELECT m::date, p.product, greatest(0, (p.base + 3 * sin(i * 1.3))::int), p.approver, 'RISK_POLICY'
FROM generate_series(DATE '2025-10-01', DATE '2026-09-01', INTERVAL '1 month') WITH ORDINALITY AS g(m, i)
CROSS JOIN (VALUES
  ('Home Loan', 9, 'Head of Retail Credit'),
  ('Car Loan', 4, 'Head of Retail Credit'),
  ('Personal Loan', 6, 'Regional credit manager')
) AS p(product, base, approver)
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW kb.product_monthly AS SELECT * FROM mart.product_monthly;
CREATE OR REPLACE VIEW kb.credit_exceptions AS SELECT * FROM mart.credit_exceptions;

-- Read-only role for Trino. LOCAL ONLY password; production uses the bank's credential vault.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ekb_reader') THEN
    CREATE ROLE ekb_reader LOGIN PASSWORD 'change_me_reader';
  END IF;
END
$$;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ekb_reader;
GRANT USAGE ON SCHEMA kb TO ekb_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA kb TO ekb_reader;
