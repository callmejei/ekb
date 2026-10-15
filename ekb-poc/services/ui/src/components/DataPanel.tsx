/**
 * Data-route result: the SQL the model wrote, the executed form (with the access-group CTEs the
 * API injected), the rows from Trino, and a simple chart when the result has a category and a
 * measure. Modelled on Prism Sage's results panel, without the charting library.
 */

import { useMemo, useState } from "react";
import { Check, Copy, Database, ShieldCheck, Warning } from "@phosphor-icons/react";
import type { DataResult } from "../api";
import { Badge } from "./ui";

export function DataPanel({ data, anchor }: { data: DataResult; anchor: string }) {
  const [executed, setExecuted] = useState(false);
  const [copied, setCopied] = useState(false);
  const sql = executed ? data.executed_sql : data.sql;

  if (!data.sql && !data.error) return null;

  return (
    <div id={anchor} className="mt-3 overflow-hidden rounded-xl border border-info/25 bg-info/5">
      <div className="flex flex-wrap items-center gap-2 border-b border-info/20 px-3 py-2 text-[11.5px]">
        <span className="flex items-center gap-1.5 font-semibold uppercase tracking-[0.06em] text-info">
          <Database size={14} /> Data query · Trino
        </span>
        {data.attempts > 1 && <Badge tone="warning">corrected after {data.attempts - 1} retry</Badge>}
        {data.blocked && <Badge tone="error">blocked by SQL guard</Badge>}
        <div className="ml-auto flex items-center gap-1">
          {data.executed_sql && (
            <button
              onClick={() => setExecuted((e) => !e)}
              className={`flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 font-semibold ${executed ? "bg-success/12 text-success" : "text-muted hover:text-text"}`}
              title="Show the SQL as executed, including the access-group filter the API injected"
            >
              <ShieldCheck size={13} /> {executed ? "Executed (with access filter)" : "Show executed SQL"}
            </button>
          )}
          {sql && (
            <button
              onClick={() => {
                navigator.clipboard?.writeText(sql);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1200);
              }}
              aria-label="Copy SQL"
              className="cursor-pointer rounded-md p-1 text-muted hover:text-text"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          )}
        </div>
      </div>

      {sql && (
        <pre className="max-h-56 overflow-auto bg-input-bg/60 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-text/90">
          {formatSql(sql)}
        </pre>
      )}

      {data.error && (
        <div className="flex items-start gap-2 px-3 py-2.5 text-[12.5px] text-error">
          <Warning size={15} className="mt-0.5 shrink-0" /> {data.error}
        </div>
      )}

      {data.columns.length > 0 && (
        <>
          <Chart data={data} />
          <div className="max-h-72 overflow-auto border-t border-info/20">
            <table className="w-full text-left text-[12px]">
              <thead className="sticky top-0 bg-surface text-[10.5px] uppercase tracking-[0.05em] text-muted">
                <tr>
                  {data.columns.map((c) => (
                    <th key={c} className="px-3 py-2 font-semibold whitespace-nowrap">
                      {c.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={i} className="border-t border-border/70">
                    {row.map((v, j) => (
                      <td key={j} className={`px-3 py-1.5 ${typeof v === "number" ? "font-mono tabular-nums" : ""}`}>
                        {v === null ? <span className="text-muted">—</span> : String(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-info/20 px-3 py-1.5 text-[11px] text-muted">
            {data.row_count === 0
              ? "No rows in the data you have access to."
              : `${data.row_count}${data.truncated ? "+" : ""} row${data.row_count === 1 ? "" : "s"}${data.truncated ? " (showing first 200)" : ""}`}
          </div>
        </>
      )}
    </div>
  );
}

/** Horizontal bars for (category, number) results — enough to make a comparison or trend legible. */
function Chart({ data }: { data: DataResult }) {
  const spec = useMemo(() => {
    if (data.rows.length < 2 || data.rows.length > 30) return null;
    const numericIdx = data.columns.findIndex((_, i) => data.rows.every((r) => typeof r[i] === "number"));
    const yIdx = data.chart.y ? data.columns.indexOf(data.chart.y) : numericIdx;
    const y = yIdx >= 0 && data.rows.every((r) => typeof r[yIdx] === "number") ? yIdx : numericIdx;
    if (y < 0) return null;
    const xIdx = data.chart.x ? data.columns.indexOf(data.chart.x) : data.columns.findIndex((_, i) => i !== y);
    const x = xIdx >= 0 && xIdx !== y ? xIdx : data.columns.findIndex((_, i) => i !== y);
    if (x < 0) return null;
    const values = data.rows.map((r) => r[y] as number);
    const max = Math.max(...values.map(Math.abs), 0);
    // A trend's story is in the movement, so its bars start just below the minimum rather than at
    // zero — otherwise 2.03% and 2.18% render as identical bars.
    const min = Math.min(...values);
    const base = data.chart.type === "line" && min > 0 ? min - (max - min) * 0.25 : 0;
    return max > 0 ? { x, y, max, base } : null;
  }, [data]);

  if (!spec) return null;
  return (
    <div className="border-t border-info/20 px-3 py-3">
      <div className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.05em] text-muted">
        {data.columns[spec.y].replace(/_/g, " ")} by {data.columns[spec.x].replace(/_/g, " ")}
        {spec.base > 0 && <span className="ml-1 normal-case tracking-normal">(axis starts at {spec.base.toFixed(2)})</span>}
      </div>
      <div className="flex flex-col gap-1">
        {data.rows.map((r, i) => {
          const v = r[spec.y] as number;
          return (
            <div key={i} className="grid grid-cols-[minmax(90px,180px)_1fr_auto] items-center gap-2 text-[11.5px]">
              <span className="truncate text-muted" title={String(r[spec.x])}>
                {String(r[spec.x])}
              </span>
              <div className="h-3.5 rounded-sm bg-border/40">
                <div className="h-full rounded-sm bg-info/70" style={{ width: `${Math.max(2, ((Math.abs(v) - spec.base) / (spec.max - spec.base)) * 100)}%` }} />
              </div>
              <span className="font-mono tabular-nums">{v.toLocaleString()}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Light formatting so generated one-line SQL reads as clauses. */
function formatSql(sql: string) {
  if (sql.includes("\n")) return sql;
  return sql.replace(/\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|JOIN|LEFT JOIN|UNION|WITH|SELECT)\s+/g, "\n$1 ").trim();
}
