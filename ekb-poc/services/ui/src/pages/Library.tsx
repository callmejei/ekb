/**
 * Library — two views of the same governed content:
 *  · Browse: active, in-date documents you can see, faceted by category / product / business unit
 *    (Elasticsearch aggregations under the same security filter as search).
 *  · Register: every document and version in your access groups with its workflow and pipeline state.
 */

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Books, CaretDown, FilePdf, FunnelSimple, MagnifyingGlass, X } from "@phosphor-icons/react";
import { api, openPdf, type BrowseDoc, type DocumentRow, type Facet } from "../api";
import { useSession } from "../session";
import { Badge, Card, Empty, PageHeader, Spinner, StatusBadge, fmtDate, fmtDateTime, inputClass } from "../components/ui";

type Tab = "browse" | "register";

export default function Library() {
  const [tab, setTab] = useState<Tab>("browse");
  return (
    <div className="mx-auto max-w-[1400px] px-6 py-7">
      <PageHeader
        title="Library"
        subtitle="Approved knowledge and its governance record."
        actions={
          <div className="flex rounded-lg border border-border bg-surface p-0.5 text-[12.5px]">
            {(["browse", "register"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`cursor-pointer rounded-md px-3 py-1.5 font-semibold ${tab === t ? "bg-accent/12 text-accent" : "text-muted hover:text-text"}`}
              >
                {t === "browse" ? "Browse" : "Document register"}
              </button>
            ))}
          </div>
        }
      />
      {tab === "browse" ? <Browse /> : <Register />}
    </div>
  );
}

const FACET_LABEL: Record<string, string> = { category: "Category", product: "Product", business_unit: "Business unit" };

function Browse() {
  const { user } = useSession();
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ facets: Record<string, Facet[]>; documents: BrowseDoc[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    const params: Record<string, string> = { ...filters };
    if (q.trim()) params.q = q.trim();
    api.browse(params).then(setData).catch(() => setData({ facets: {}, documents: [] }));
  }, [filters, q]);

  useEffect(() => {
    const id = window.setTimeout(load, q ? 250 : 0);
    return () => window.clearTimeout(id);
  }, [load, q, user?.username]);

  return (
    <div className="grid gap-5 lg:grid-cols-[250px_1fr]">
      <aside className="flex flex-col gap-4">
        <div className="relative">
          <MagnifyingGlass size={15} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search content…" className={`${inputClass} pl-9`} />
        </div>
        {(["category", "product", "business_unit"] as const).map((f) => (
          <div key={f}>
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">
              <FunnelSimple size={12} /> {FACET_LABEL[f]}
            </div>
            <div className="flex flex-col gap-0.5">
              {(data?.facets[f] ?? []).map((b) => {
                const on = filters[f] === b.value;
                return (
                  <button
                    key={b.value}
                    onClick={() => setFilters((x) => (on ? omit(x, f) : { ...x, [f]: b.value }))}
                    className={`flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-left text-[12.5px] transition-colors ${
                      on ? "bg-accent/12 font-semibold text-accent" : "hover:bg-surface-2"
                    }`}
                  >
                    <span className="truncate">{b.value}</span>
                    <span className="font-mono text-[11px] text-muted">{b.count}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </aside>

      <div>
        {Object.keys(filters).length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {Object.entries(filters).map(([k, v]) => (
              <button key={k} onClick={() => setFilters((x) => omit(x, k))} className="cursor-pointer">
                <Badge tone="accent">
                  {FACET_LABEL[k]}: {v} <X size={11} weight="bold" />
                </Badge>
              </button>
            ))}
          </div>
        )}
        {!data ? (
          <div className="flex justify-center py-20 text-muted">
            <Spinner />
          </div>
        ) : data.documents.length === 0 ? (
          <Card>
            <Empty icon={<Books size={24} />} title="No documents match" body="Try clearing a filter. Only active, in-date documents in your access groups are listed." />
          </Card>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {data.documents.map((d) => (
              <Card key={d.version_id} className="flex flex-col p-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                    <FilePdf size={20} weight="duotone" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <button onClick={() => openPdf(d.version_id)} className="cursor-pointer text-left text-[14px] font-bold hover:text-accent">
                      {d.title}
                    </button>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <Badge tone="info">{d.category}</Badge>
                      {d.product && <Badge>{d.product}</Badge>}
                      <Badge tone={d.access_group === "RISK_POLICY" ? "warning" : "muted"}>{d.access_group}</Badge>
                      <span className="font-mono text-[11px] text-muted">
                        v{d.version_no} · effective {fmtDate(d.effective_date)}
                      </span>
                    </div>
                  </div>
                </div>
                {d.summary && <p className="mt-3 text-[12.5px] leading-relaxed text-muted">{d.summary}</p>}
                <button
                  onClick={() => setOpen(open === d.version_id ? null : d.version_id)}
                  className="mt-2 flex cursor-pointer items-center gap-1 self-start text-[12px] font-semibold text-muted hover:text-text"
                >
                  <CaretDown size={12} className={`transition-transform ${open === d.version_id ? "rotate-180" : ""}`} /> Key information & sample Q&A
                </button>
                <AnimatePresence>
                  {open === d.version_id && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <dl className="mt-2 grid grid-cols-[140px_1fr] gap-y-1 text-[12px]">
                        {Object.entries(d.key_info).map(([k, v]) => (
                          <div key={k} className="contents">
                            <dt className="text-muted capitalize">{k.replace(/_/g, " ")}</dt>
                            <dd>{v}</dd>
                          </div>
                        ))}
                      </dl>
                      <div className="mt-3 flex flex-col gap-2">
                        {d.sample_qa.slice(0, 3).map((qa) => (
                          <div key={qa.question} className="rounded-lg bg-surface-2 p-2.5 text-[12px]">
                            <div className="font-semibold">{qa.question}</div>
                            <div className="text-muted">{qa.answer}</div>
                          </div>
                        ))}
                      </div>
                      {d.entities.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1">
                          {d.entities.map((e) => (
                            <Badge key={e.name + e.type} tone="graph">
                              {e.type}: {e.name}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function omit(o: Record<string, string>, k: string) {
  const { [k]: _, ...rest } = o;
  return rest;
}

function Register() {
  const { user } = useSession();
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);

  useEffect(() => {
    const load = () => api.documents().then(setDocs).catch(() => setDocs([]));
    load();
    const id = window.setInterval(load, 5000); // pipeline progress
    return () => window.clearInterval(id);
  }, [user?.username]);

  if (!docs)
    return (
      <div className="flex justify-center py-20 text-muted">
        <Spinner />
      </div>
    );

  return (
    <Card className="overflow-x-auto">
      <table className="w-full min-w-[980px] text-left text-[12.5px]">
        <thead className="border-b border-border text-[11px] uppercase tracking-[0.05em] text-muted">
          <tr>
            {["Document", "Version", "Status", "Pipeline", "Category", "Access group", "Effective", "Uploaded"].map((h) => (
              <th key={h} className="px-4 py-3 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {docs.flatMap((d) =>
            d.versions.map((v, i) => (
              <tr key={v.version_id} className={`border-b border-border last:border-0 ${v.status === "SUPERSEDED" ? "opacity-60" : ""}`}>
                <td className="px-4 py-2.5">
                  {i === 0 ? (
                    <button onClick={() => openPdf(v.version_id)} className="cursor-pointer text-left font-semibold hover:text-accent">
                      {d.title}
                    </button>
                  ) : (
                    <span className="pl-3 text-muted">↳ earlier version</span>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono">v{v.version_no}</td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={v.status} />
                </td>
                <td className="px-4 py-2.5">
                  <Pipeline v={v} />
                </td>
                <td className="px-4 py-2.5">{d.category}</td>
                <td className="px-4 py-2.5 font-mono text-[11.5px]">{d.access_group}</td>
                <td className="whitespace-nowrap px-4 py-2.5">{fmtDate(v.effective_date)}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">
                  {v.uploaded_by} · {fmtDateTime(v.created_at)}
                </td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </Card>
  );
}

function Pipeline({ v }: { v: DocumentRow["versions"][number] }) {
  const s = v.pipeline_status;
  if (!s) return <span className="text-muted">—</span>;
  if (s === "DONE")
    return (
      <span className="whitespace-nowrap font-mono text-[11.5px] text-success">
        indexed · {v.page_count}p · {v.chunk_count} chunks
      </span>
    );
  if (s === "FAILED") return <span className="text-[11.5px] text-error" title={v.pipeline_error ?? ""}>failed</span>;
  return (
    <span className="flex items-center gap-1.5 font-mono text-[11.5px] text-warning">
      <span className="breathe inline-block h-1.5 w-1.5 rounded-full bg-warning" />
      {s.replace("RUNNING:", "").toLowerCase()}
    </span>
  );
}
