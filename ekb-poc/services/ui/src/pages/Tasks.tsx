/**
 * Approvals — the checker side of maker-checker. Pending tasks for the signed-in role on the left;
 * the selected document's preview, metadata, conflict check and decision on the right.
 * Batch uploads can be approved as one manifest.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUUpLeft, CheckCircle, CheckSquareOffset, Copy, Prohibit, Stack, Warning } from "@phosphor-icons/react";
import { api, openPdf, pageImages, type Task } from "../api";
import { ROLE_LABEL, useSession } from "../session";
import { Badge, Button, Card, Empty, PageHeader, Spinner, fmtDate, fmtDateTime, inputClass } from "../components/ui";

const STEP_LABEL: Record<string, string> = { VERIFY: "Verify", APPROVE: "Approve", ACKNOWLEDGE: "Acknowledge" };
const FLOW = ["UPLOAD", "VERIFY", "APPROVE", "ACKNOWLEDGE", "ACTIVE"];

export default function Tasks() {
  const { user, refreshStats } = useSession();
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [toast, setToast] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const load = useCallback(() => {
    api
      .tasks()
      .then((t) => {
        setTasks(t);
        setSelected((s) => (s && t.some((x) => x.task_id === s) ? s : t[0]?.task_id ?? null));
      })
      .catch((e) => setToast({ tone: "error", text: e.message }));
  }, []);

  useEffect(load, [load, user?.username]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const batches = useMemo(() => {
    const m = new Map<string, Task[]>();
    tasks?.forEach((t) => t.batch_id && m.set(t.batch_id, [...(m.get(t.batch_id) ?? []), t]));
    return [...m.entries()].filter(([, ts]) => ts.length > 1);
  }, [tasks]);

  const current = tasks?.find((t) => t.task_id === selected) ?? null;

  async function decide(task: Task, decision: string, comment: string) {
    try {
      await api.decide(task.task_id, decision, comment);
      setToast({
        tone: "success",
        text:
          decision === "APPROVED"
            ? task.step === "ACKNOWLEDGE"
              ? `Acknowledged — "${task.title}" is being indexed and will go live shortly.`
              : `${STEP_LABEL[task.step]} done — sent to the next reviewer.`
            : `${decision.toLowerCase()} — the requestor has been notified.`,
      });
      load();
      refreshStats();
    } catch (e) {
      setToast({ tone: "error", text: (e as Error).message });
    }
  }

  async function decideBatch(batchId: string, count: number) {
    try {
      await api.decideBatch(batchId, "APPROVED", "Batch manifest approved");
      setToast({ tone: "success", text: `Batch of ${count} documents approved.` });
      load();
      refreshStats();
    } catch (e) {
      setToast({ tone: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-7">
      <PageHeader
        title="Approvals"
        subtitle={
          <>
            Pending tasks for your role: <b className="text-text">{user?.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</b>. Every
            decision is written to the audit trail.
          </>
        }
      />

      {toast && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className={`mb-4 rounded-xl px-4 py-3 text-[13px] ${toast.tone === "success" ? "bg-success/10 text-success" : "bg-error/10 text-error"}`}
        >
          {toast.text}
        </motion.div>
      )}

      {batches.map(([batchId, ts]) => (
        <Card key={batchId} className="mb-4 flex flex-wrap items-center gap-3 p-4">
          <Stack size={20} className="text-info" />
          <div className="flex-1">
            <div className="text-[13.5px] font-semibold">Batch manifest · {ts.length} documents</div>
            <div className="text-[12px] text-muted">{ts.map((t) => t.title).join(" · ")}</div>
          </div>
          <Button variant="primary" size="sm" disabled={ts.some((t) => t.self_upload)} onClick={() => decideBatch(batchId, ts.length)}>
            <CheckCircle size={15} weight="bold" /> Approve batch
          </Button>
        </Card>
      ))}

      {!tasks ? (
        <div className="flex justify-center py-20 text-muted">
          <Spinner />
        </div>
      ) : tasks.length === 0 ? (
        <Card>
          <Empty icon={<CheckSquareOffset size={24} />} title="Nothing waiting for you" body="New uploads appear here when they reach your step." />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="flex flex-col gap-2">
            {tasks.map((t) => {
              const near = t.conflict?.near_duplicates.filter((n) => n.flag === "near_duplicate").length ?? 0;
              return (
                <button
                  key={t.task_id}
                  onClick={() => setSelected(t.task_id)}
                  className={`tap cursor-pointer rounded-xl border p-3 text-left transition-colors ${
                    selected === t.task_id ? "border-accent/50 bg-accent/5" : "border-border bg-surface hover:border-accent/30"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="info">{STEP_LABEL[t.step]}</Badge>
                    {t.version_no > 1 && <Badge tone="warning">new version v{t.version_no}</Badge>}
                    {near > 0 && (
                      <Badge tone="error">
                        <Warning size={11} weight="fill" /> near-duplicate
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1.5 text-[13.5px] font-semibold">{t.title}</div>
                  <div className="text-[11.5px] text-muted">
                    {t.category} · {t.business_unit} · by {t.uploaded_by} · {fmtDateTime(t.uploaded_at)}
                  </div>
                </button>
              );
            })}
          </div>
          {current && <TaskDetail key={current.task_id} task={current} onDecide={decide} />}
        </div>
      )}
    </div>
  );
}

function TaskDetail({ task, onDecide }: { task: Task; onDecide: (t: Task, d: string, c: string) => Promise<void> }) {
  const [pages, setPages] = useState<string[] | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let urls: string[] = [];
    pageImages(task.version_id)
      .then((u) => {
        urls = u;
        setPages(u);
      })
      .catch(() => setPages([]));
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [task.version_id]);

  const near = task.conflict?.near_duplicates ?? [];
  const stepIndex = FLOW.indexOf(task.step);

  async function go(decision: string) {
    setBusy(decision);
    await onDecide(task, decision, comment);
    setBusy(null);
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card className="flex flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5 text-[12px] text-muted">
          <span>Preview · {pages ? pages.length : "…"} page(s)</span>
          <button onClick={() => openPdf(task.version_id)} className="cursor-pointer font-semibold hover:text-accent">
            Open PDF
          </button>
        </div>
        {pages ? (
          <div className="flex h-[calc(100dvh-270px)] min-h-[520px] flex-col items-center gap-4 overflow-y-auto bg-surface-2 p-4">
            {pages.map((src, i) => (
              <img key={src} src={src} alt={`Page ${i + 1}`} className="w-full max-w-[720px] rounded-md shadow-[var(--shadow-pop)]" />
            ))}
          </div>
        ) : (
          <div className="flex h-[520px] items-center justify-center text-muted">
            <Spinner />
          </div>
        )}
      </Card>

      <div className="flex flex-col gap-4">
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-1">
            {FLOW.map((s, i) => (
              <div key={s} className="flex flex-1 flex-col items-center gap-1">
                <div className={`h-1.5 w-full rounded-full ${i < stepIndex ? "bg-success" : i === stepIndex ? "bg-accent" : "bg-border"}`} />
                <span className={`text-[10px] font-semibold uppercase tracking-[0.04em] ${i === stepIndex ? "text-accent" : "text-muted"}`}>
                  {s.toLowerCase()}
                </span>
              </div>
            ))}
          </div>
          <div className="text-[15px] font-bold">{task.title}</div>
          <div className="mb-3 text-[12px] text-muted">
            {task.file_name} · version {task.version_no}
          </div>
          <dl className="grid grid-cols-[120px_1fr] gap-y-1.5 text-[12.5px]">
            {[
              ["Country", task.country],
              ["Business unit", task.business_unit],
              ["Category", task.category],
              ["Product", task.product ?? "—"],
              ["Access group", <span className="font-mono">{task.access_group}</span>],
              ["Effective", fmtDate(task.effective_date)],
              ["Expiry", fmtDate(task.expiry_date)],
              ["Uploaded by", task.uploaded_by],
            ].map(([k, v]) => (
              <div key={String(k)} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card className="p-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">Content conflict check</div>
          <div className="flex items-center gap-2 text-[12.5px]">
            <CheckCircle size={16} weight="fill" className="text-success" /> No exact duplicate (SHA-256)
          </div>
          {near.length === 0 ? (
            <div className="mt-1.5 flex items-center gap-2 text-[12.5px]">
              <CheckCircle size={16} weight="fill" className="text-success" /> No similar active documents in {task.category}
            </div>
          ) : (
            near.map((n) => (
              <div
                key={n.version_id}
                className={`mt-2 rounded-lg p-2.5 text-[12.5px] ${n.flag === "near_duplicate" ? "bg-error/10 text-error" : "bg-warning/10 text-warning"}`}
              >
                <div className="flex items-center gap-1.5 font-semibold">
                  {n.flag === "near_duplicate" ? <Copy size={14} weight="bold" /> : <Warning size={14} weight="bold" />}
                  {n.flag === "near_duplicate" ? "Near-duplicate of" : "Similar to"} "{n.title}" v{n.version_no}
                </div>
                <div className="mt-0.5 font-mono text-[11.5px] opacity-85">
                  text overlap {((n.text_overlap ?? 0) * 100).toFixed(0)}% · semantic {((n.semantic ?? n.similarity) * 100).toFixed(0)}%
                </div>
              </div>
            ))
          )}
        </Card>

        <Card className="p-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">Your decision · {STEP_LABEL[task.step]}</div>
          {task.self_upload && (
            <div className="mb-3 rounded-lg bg-warning/10 p-2.5 text-[12.5px] text-warning">
              Segregation of duties: you uploaded this document, so you cannot review it.
            </div>
          )}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment (recorded in the audit trail)"
            rows={2}
            className={`${inputClass} h-auto py-2`}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" loading={busy === "APPROVED"} disabled={!!busy} onClick={() => go("APPROVED")} className="flex-1">
              <CheckCircle size={16} weight="bold" /> {task.step === "ACKNOWLEDGE" ? "Acknowledge & publish" : STEP_LABEL[task.step]}
            </Button>
            <Button variant="secondary" loading={busy === "RETURNED"} disabled={!!busy} onClick={() => go("RETURNED")}>
              <ArrowUUpLeft size={15} /> Return
            </Button>
            <Button variant="danger" loading={busy === "REJECTED"} disabled={!!busy} onClick={() => go("REJECTED")}>
              <Prohibit size={15} /> Reject
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
