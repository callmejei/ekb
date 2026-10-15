import { useEffect, useMemo, useState } from "react";
import { ShieldCheck } from "@phosphor-icons/react";
import { api, type AuditRow } from "../api";
import { Badge, Card, Empty, PageHeader, Spinner, fmtDateTime, type Tone } from "../components/ui";

const ACTION_TONE: Record<string, Tone> = {
  UPLOAD: "info",
  BULK_UPLOAD: "info",
  VERIFY: "success",
  APPROVE: "success",
  ACKNOWLEDGE: "success",
  BATCH_DECISION: "success",
  QUERY: "accent",
  LLM_CALL: "graph",
  DUPLICATE_BLOCKED: "error",
  SOD_VIOLATION_BLOCKED: "error",
  PIPELINE_FAILED: "error",
  PIPELINE_DONE: "success",
  FEEDBACK: "warning",
  SQL_EXECUTE: "info",
  SQL_ERROR: "warning",
  SQL_BLOCKED: "error",
};

function summary(r: AuditRow): string {
  const d = r.details as Record<string, unknown>;
  switch (r.action) {
    case "QUERY":
      return `"${d.question}" · route ${d.route} · ${(d.chunk_ids as string[] | undefined)?.length ?? 0} chunks · ${d.latency_ms}ms · groups ${(d.access_groups as string[] | undefined)?.join(", ")}`;
    case "LLM_CALL":
      return `${d.model} · ${d.latency_ms}ms${d.usage ? ` · ${(d.usage as { total_tokens?: number }).total_tokens ?? "?"} tokens` : ""}`;
    case "VERIFY":
    case "APPROVE":
    case "ACKNOWLEDGE":
      return `${d.decision}${d.comment ? ` — ${d.comment}` : ""}`;
    case "UPLOAD":
      return `${d.file} · v${d.version_no} · sha256 ${String(d.sha256).slice(0, 12)}…`;
    case "SQL_EXECUTE":
      return `${d.rows} rows · attempt ${d.attempt} · ${d.latency_ms}ms · ${String(d.sql).replace(/\s+/g, " ").slice(0, 140)}`;
    case "SQL_BLOCKED":
      return `${d.reason} · ${String(d.sql).slice(0, 100)}`;
    case "PIPELINE_DONE":
      return `${d.pages} pages · ${d.chunks} chunks · ${d.tables} tables`;
    default:
      return Object.keys(d).length ? JSON.stringify(d).slice(0, 160) : "";
  }
}

export default function Audit() {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState("");

  useEffect(() => {
    const load = () => api.audit().then(setRows).catch((e) => setError(e.message));
    load();
    const id = window.setInterval(load, 6000);
    return () => window.clearInterval(id);
  }, []);

  const actions = useMemo(() => [...new Set(rows?.map((r) => r.action))].sort(), [rows]);
  const shown = rows?.filter((r) => !action || r.action === action) ?? [];

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-7">
      <PageHeader
        title="Audit trail"
        subtitle="Append-only record of every workflow action, query and model call. Updates and deletes are blocked at the database."
        actions={
          <select value={action} onChange={(e) => setAction(e.target.value)} className="h-9 rounded-lg border border-border bg-surface px-3 text-[12.5px]">
            <option value="">All actions</option>
            {actions.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        }
      />
      {error && <div className="rounded-xl bg-error/10 p-3 text-[13px] text-error">{error}</div>}
      {!rows && !error ? (
        <div className="flex justify-center py-20 text-muted">
          <Spinner />
        </div>
      ) : shown.length === 0 && !error ? (
        <Card>
          <Empty icon={<ShieldCheck size={24} />} title="No audit records yet" />
        </Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-[12.5px]">
            <thead className="border-b border-border text-[11px] uppercase tracking-[0.05em] text-muted">
              <tr>
                {["#", "Time", "Actor", "Action", "Object", "Details"].map((h) => (
                  <th key={h} className="px-4 py-3 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.audit_id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono text-muted">{r.audit_id}</td>
                  <td className="px-4 py-2 whitespace-nowrap text-muted">{fmtDateTime(r.ts)}</td>
                  <td className="px-4 py-2 font-semibold">{r.actor}</td>
                  <td className="px-4 py-2">
                    <Badge tone={ACTION_TONE[r.action] ?? "muted"}>{r.action}</Badge>
                  </td>
                  <td className="max-w-[160px] truncate px-4 py-2 font-mono text-[11px] text-muted">{r.object_ref}</td>
                  <td className="max-w-[560px] truncate px-4 py-2 text-muted" title={JSON.stringify(r.details)}>
                    {summary(r)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
