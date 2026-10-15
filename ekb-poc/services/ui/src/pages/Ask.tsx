/**
 * Ask — chat over the knowledge base. Each answer shows inline citation markers, the cited sources
 * (document · version · page, click to open the PDF at that page), the graph context used, and a
 * retrieval trace so the demo can show *why* an answer came back.
 */

import { Fragment, memo, useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowSquareOut,
  ChatCircleText,
  Graph,
  Lightning,
  ListMagnifyingGlass,
  PaperPlaneTilt,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Trash,
} from "@phosphor-icons/react";
import { api, openPdf, type Citation, type QueryResponse } from "../api";
import { useSession } from "../session";
import { Badge } from "../components/ui";
import { DataPanel } from "../components/DataPanel";

const STARTERS = [
  "What is the prepayment penalty on the home loan and when does it apply?",
  "What rules apply when we lend to a customer for a car loan?",
  "What discount can a branch manager give on a home loan?",
  "Which products have a late payment charge above SGD 90?",
  "Show the monthly arrears rate trend for personal loans",
  "What is the latest arrears rate on credit cards, and what is the credit card late payment fee?",
];

type RouteChoice = "auto" | "document" | "data";

interface Turn {
  id: string;
  question: string;
  mode: string;
  route: RouteChoice;
  response: QueryResponse | null;
  error: string | null;
  feedback: 1 | -1 | 0;
}

export default function Ask() {
  const { user } = useSession();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<"hybrid_graph" | "hybrid">("hybrid_graph");
  const [route, setRoute] = useState<RouteChoice>("auto");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Conversations are per user — switching identity for the security demo starts clean.
  useEffect(() => setTurns([]), [user?.username]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const id = crypto.randomUUID();
    setTurns((t) => [...t, { id, question: q, mode, route, response: null, error: null, feedback: 0 }]);
    setDraft("");
    setBusy(true);
    try {
      const response = await api.query(q, mode, route);
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x)));
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: (e as Error).message } : x)));
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function rate(id: string, traceId: string, rating: 1 | -1) {
    setTurns((t) => t.map((x) => (x.id === id ? { ...x, feedback: rating } : x)));
    api.feedback(traceId, rating).catch(() => undefined);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[920px] px-6 py-8">
          {turns.length === 0 ? (
            <Welcome onPick={ask} groups={user?.access_groups ?? []} />
          ) : (
            <div className="flex flex-col gap-8">
              {turns.map((t) => (
                <TurnView key={t.id} turn={t} onRate={(r) => t.response && rate(t.id, t.response.trace_id, r)} />
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border bg-surface/80 backdrop-blur">
        <div className="mx-auto w-full max-w-[920px] px-6 py-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask(draft);
            }}
            className="flex items-end gap-2 rounded-[14px] border border-border bg-input-bg p-2 focus-within:border-accent/60"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(draft);
                }
              }}
              rows={1}
              placeholder="Ask about products, fees, policies…"
              className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[14px] outline-none placeholder:text-muted/70 focus-visible:outline-none"
            />
            <button
              type="submit"
              disabled={!draft.trim() || busy}
              aria-label="Send"
              className="tap flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-[10px] bg-accent text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              <PaperPlaneTilt size={18} weight="fill" />
            </button>
          </form>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11.5px] text-muted">
            <div className="flex rounded-lg border border-border p-0.5" role="radiogroup" aria-label="Route">
              {(
                [
                  ["auto", "Auto route"],
                  ["document", "Documents"],
                  ["data", "Data (SQL)"],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  role="radio"
                  aria-checked={route === m}
                  onClick={() => setRoute(m)}
                  className={`cursor-pointer rounded-md px-2.5 py-1 font-semibold transition-colors ${
                    route === m ? "bg-info/12 text-info" : "hover:text-text"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-border p-0.5" role="radiogroup" aria-label="Retrieval mode">
              {(
                [
                  ["hybrid_graph", "Hybrid + graph"],
                  ["hybrid", "Hybrid only"],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  role="radio"
                  aria-checked={mode === m}
                  onClick={() => setMode(m)}
                  className={`cursor-pointer rounded-md px-2.5 py-1 font-semibold transition-colors ${
                    mode === m ? "bg-accent/12 text-accent" : "hover:text-text"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="flex items-center gap-1">
              <ShieldCheck size={13} /> Results trimmed to <span className="font-mono">{user?.access_groups.join(", ")}</span>
            </span>
            {turns.length > 0 && (
              <button onClick={() => setTurns([])} className="ml-auto flex cursor-pointer items-center gap-1 hover:text-text">
                <Trash size={13} /> Clear
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Welcome({ onPick, groups }: { onPick: (q: string) => void; groups: string[] }) {
  return (
    <div className="flex flex-col items-center pt-10 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/12 text-accent">
        <ChatCircleText size={28} weight="duotone" />
      </div>
      <h1 className="text-[24px] font-extrabold tracking-[-0.02em]">What do you need to know?</h1>
      <p className="mt-2 max-w-lg text-[13.5px] text-muted">
        Answers come only from approved, active documents in your access groups ({groups.join(", ")}), with the
        document, version and page cited for every statement.
      </p>
      <div className="mt-8 grid w-full max-w-[760px] gap-2.5 sm:grid-cols-2">
        {STARTERS.map((s, i) => (
          <motion.button
            key={s}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            onClick={() => onPick(s)}
            className="tap cursor-pointer rounded-xl border border-border bg-surface p-3.5 text-left text-[13px] transition-colors hover:border-accent/40"
          >
            {s}
          </motion.button>
        ))}
      </div>
    </div>
  );
}

const TurnView = memo(function TurnView({ turn, onRate }: { turn: Turn; onRate: (r: 1 | -1) => void }) {
  const r = turn.response;
  const [showTrace, setShowTrace] = useState(false);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-[14px] rounded-br-md bg-accent px-4 py-2.5 text-[14px] text-white">{turn.question}</div>
      </div>

      <div className="flex gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-accent">
          <Lightning size={16} weight="fill" />
        </div>
        <div className="min-w-0 flex-1">
          {!r && !turn.error && <Thinking mode={turn.mode} route={turn.route} />}
          {turn.error && <div className="rounded-xl bg-error/10 p-3 text-[13px] text-error">{turn.error}</div>}
          {r && (
            <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
              <div className="rounded-[14px] rounded-tl-md border border-border bg-surface px-4 py-3.5">
                <Answer text={r.answer} citations={r.citations} dataAnchor={`data-${turn.id}`} />
              </div>

              {r.citations.length > 0 && (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {r.citations.map((c) => (
                    <SourceCard key={c.n} c={c} />
                  ))}
                </div>
              )}

              {r.data && <DataPanel data={r.data} anchor={`data-${turn.id}`} />}

              {r.mode === "hybrid_graph" && r.graph.relations.length + r.graph.entities.length > 0 && (
                <GraphContext graph={r.graph} />
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
                <span title={r.route_reason}>
                  <Badge tone={r.route === "data" ? "info" : r.route === "mixed" ? "warning" : "accent"}>route: {r.route}</Badge>
                </span>
                {r.route !== "data" && (
                  <Badge tone={r.mode === "hybrid_graph" ? "graph" : "muted"}>{r.mode === "hybrid_graph" ? "hybrid + graph" : "hybrid only"}</Badge>
                )}
                <span className="font-mono">{(r.latency_ms / 1000).toFixed(1)}s</span>
                <span className="font-mono">{r.model}</span>
                <span className="font-mono opacity-70">trace {r.trace_id}</span>
                {r.retrieved.length > 0 && (
                  <button
                    onClick={() => setShowTrace((s) => !s)}
                    className="flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-surface-2 hover:text-text"
                  >
                    <ListMagnifyingGlass size={13} /> {showTrace ? "Hide" : "Show"} retrieval
                  </button>
                )}
                <div className="ml-auto flex items-center gap-1">
                  <button
                    aria-label="Helpful"
                    onClick={() => onRate(1)}
                    className={`cursor-pointer rounded-md p-1.5 hover:bg-surface-2 ${turn.feedback === 1 ? "text-success" : ""}`}
                  >
                    <ThumbsUp size={15} weight={turn.feedback === 1 ? "fill" : "regular"} />
                  </button>
                  <button
                    aria-label="Not helpful"
                    onClick={() => onRate(-1)}
                    className={`cursor-pointer rounded-md p-1.5 hover:bg-surface-2 ${turn.feedback === -1 ? "text-error" : ""}`}
                  >
                    <ThumbsDown size={15} weight={turn.feedback === -1 ? "fill" : "regular"} />
                  </button>
                </div>
              </div>
              <AnimatePresence>{showTrace && <Trace r={r} />}</AnimatePresence>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
});

function Thinking({ mode, route }: { mode: string; route: RouteChoice }) {
  const docSteps = ["Hybrid search (BM25 + kNN)", ...(mode === "hybrid_graph" ? ["Graph expansion"] : [])];
  const dataSteps = ["Writing SQL", "Running on Trino"];
  const steps = [
    ...(route === "auto" ? ["Routing question"] : []),
    ...(route === "data" ? dataSteps : route === "document" ? docSteps : [...docSteps, ...dataSteps]),
    "Generating grounded answer",
  ];
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 1100);
    return () => window.clearInterval(id);
  }, [steps.length]);
  return (
    <div className="rounded-[14px] rounded-tl-md border border-border bg-surface px-4 py-3.5">
      <div className="mb-3 flex items-center gap-2 text-[12.5px] text-muted">
        <span className="breathe inline-block h-2 w-2 rounded-full bg-accent" />
        {steps[i]}…
      </div>
      <div className="flex flex-col gap-2">
        {[92, 78, 64].map((w) => (
          <div key={w} className="shimmer h-3 rounded" style={{ width: `${w}%` }} />
        ))}
      </div>
    </div>
  );
}

/** Minimal markdown (paragraphs, bullets, bold) with [n] markers turned into citation chips. */
function Answer({ text, citations, dataAnchor }: { text: string; citations: Citation[]; dataAnchor: string }) {
  const byN = new Map(citations.map((c) => [c.n, c]));
  const inline = (s: string): ReactNode[] =>
    s.split(/(\*\*[^*]+\*\*|\[\d+\]|\[SQL\])/g).map((part, i) => {
      if (part === "[SQL]") {
        return (
          <button
            key={i}
            title="From the data query — jump to the SQL and result"
            onClick={() => document.getElementById(dataAnchor)?.scrollIntoView({ behavior: "smooth", block: "center" })}
            className="mx-0.5 inline-flex h-[18px] cursor-pointer items-center justify-center rounded-[5px] bg-info/14 px-1 align-[1px] font-mono text-[10px] font-bold text-info hover:bg-info hover:text-white"
          >
            SQL
          </button>
        );
      }
      const cite = part.match(/^\[(\d+)\]$/);
      if (cite) {
        const c = byN.get(Number(cite[1]));
        return (
          <button
            key={i}
            title={c ? `${c.title} · v${c.version_no} · p.${c.page}` : undefined}
            onClick={() => c && openPdf(c.version_id, c.page)}
            className="mx-0.5 inline-flex h-[18px] min-w-[18px] cursor-pointer items-center justify-center rounded-[5px] bg-accent/14 px-1 align-[1px] font-mono text-[10.5px] font-bold text-accent hover:bg-accent hover:text-white"
          >
            {cite[1]}
          </button>
        );
      }
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
      return <Fragment key={i}>{part}</Fragment>;
    });

  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let ordered = false;
  const flush = () => {
    if (!list.length) return;
    const items = list.map((l, i) => <li key={i}>{inline(l)}</li>);
    blocks.push(ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
    list = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)/);
    const num = line.match(/^\d+[.)]\s+(.*)/);
    if (bullet || num) {
      if (list.length && ordered !== !!num) flush();
      ordered = !!num;
      list.push((bullet ?? num)![1]);
    } else {
      flush();
      if (line) blocks.push(<p key={blocks.length}>{inline(line.replace(/^#+\s*/, ""))}</p>);
    }
  }
  flush();
  return <div className="answer text-[14px] leading-relaxed">{blocks}</div>;
}

/** Table chunks are stored as Markdown; drop the pipe/rule syntax for a readable one-line preview. */
function cleanSnippet(s: string) {
  return s
    .replace(/\|\s*-{3,}\s*/g, "")
    .replace(/\s*\|\s*/g, " · ")
    .replace(/(· )+/g, "· ")
    .replace(/^Table:\s*/, "")
    .trim();
}

function SourceCard({ c }: { c: Citation }) {
  return (
    <button
      onClick={() => openPdf(c.version_id, c.page)}
      className="group tap flex cursor-pointer flex-col gap-1 rounded-xl border border-border bg-surface-2 p-3 text-left transition-colors hover:border-accent/40"
    >
      <div className="flex items-center gap-2">
        <span className="flex h-5 min-w-5 items-center justify-center rounded-[5px] bg-accent/14 px-1 font-mono text-[10.5px] font-bold text-accent">
          {c.n}
        </span>
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold">{c.title}</span>
        <ArrowSquareOut size={14} className="shrink-0 text-muted group-hover:text-accent" />
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        <span className="font-mono">v{c.version_no}</span>·<span className="font-mono">page {c.page}</span>
        {c.origin === "graph" && (
          <Badge tone="graph">
            <Graph size={11} /> via graph{c.via.length ? `: ${c.via.slice(0, 2).join(", ")}` : ""}
          </Badge>
        )}
      </div>
      <div className="truncate text-[11px] text-muted">{c.heading_path.split(" > ").slice(1).join(" › ")}</div>
      <div className="line-clamp-2 text-[12px] text-text/80">{cleanSnippet(c.snippet)}</div>
    </button>
  );
}

const TYPE_TONE: Record<string, "graph" | "info" | "warning" | "muted"> = {
  Product: "info",
  Policy: "graph",
  Regulation: "warning",
};

function GraphContext({ graph }: { graph: QueryResponse["graph"] }) {
  return (
    <div className="mt-3 rounded-xl border border-graph/25 bg-graph/5 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-graph">
        <Graph size={14} /> Knowledge graph context
      </div>
      <div className="flex flex-wrap gap-1.5">
        {graph.entities.map((e) => (
          <Badge key={e.name + e.type} tone={TYPE_TONE[e.type] ?? "muted"}>
            {e.type}: {e.name}
          </Badge>
        ))}
      </div>
      {graph.relations.length > 0 && (
        <div className="mt-2 flex flex-col gap-1 font-mono text-[11.5px] text-muted">
          {graph.relations.slice(0, 8).map((r, i) => (
            <div key={i}>
              <span className="text-text">{r.source}</span> <span className="text-graph">─{r.rel}→</span>{" "}
              <span className="text-text">{r.target}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Trace({ r }: { r: QueryResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="overflow-hidden"
    >
      <div className="mt-2 rounded-xl border border-border bg-surface p-3">
        <div className="mb-2 flex flex-wrap gap-3 font-mono text-[11px] text-muted">
          {Object.entries(r.timings).map(([k, v]) => (
            <span key={k}>
              {k} <span className="text-text">{v}ms</span>
            </span>
          ))}
        </div>
        <table className="w-full text-left text-[11.5px]">
          <thead className="text-muted">
            <tr>
              <th className="py-1 pr-2 font-semibold">#</th>
              <th className="py-1 pr-2 font-semibold">Source</th>
              <th className="py-1 pr-2 font-semibold">Page</th>
              <th className="py-1 pr-2 font-semibold">Origin</th>
              <th className="py-1 pr-2 font-semibold">BM25 / kNN rank</th>
              <th className="py-1 font-semibold">Access group</th>
            </tr>
          </thead>
          <tbody>
            {r.retrieved.map((c, i) => (
              <tr key={c.chunk_id} className="border-t border-border">
                <td className="py-1 pr-2 font-mono text-muted">{i + 1}</td>
                <td className="max-w-[300px] truncate py-1 pr-2">
                  {c.title} <span className="text-muted">v{c.version_no}</span>
                </td>
                <td className="py-1 pr-2 font-mono">{c.page}</td>
                <td className="py-1 pr-2">
                  <Badge tone={c.origin === "graph" ? "graph" : "info"}>{c.origin}</Badge>
                </td>
                <td className="py-1 pr-2 font-mono text-muted">
                  {c.origin === "graph" ? `via ${c.via?.slice(0, 2).join(", ")}` : `${c.ranks?.bm25 ?? "–"} / ${c.ranks?.knn ?? "–"}`}
                </td>
                <td className="py-1 font-mono text-muted">{c.access_group}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
