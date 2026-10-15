/** Upload — the maker side: a PDF plus the metadata standard, optionally as a new version of an
 * existing document. Exact duplicates are blocked on the spot; near-duplicates are flagged to the steward. */

import { useEffect, useRef, useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { CheckCircle, CloudArrowUp, FilePdf, Prohibit, Warning } from "@phosphor-icons/react";
import { ApiError, api, type Conflict, type DocumentRow } from "../api";
import { useSession } from "../session";
import { Button, Card, Field, PageHeader, inputClass } from "../components/ui";

const CATEGORIES = ["Loans", "CFS", "Funding", "Insurance", "Policy"];
const UNITS = ["Retail Banking", "Cards and Payments", "Bancassurance", "Group Risk Management", "Group Compliance"];

interface Result {
  kind: "ok" | "duplicate" | "error";
  text: string;
  conflict?: Conflict;
  versionNo?: number;
}

export default function Upload() {
  const { user, refreshStats } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [newVersionOf, setNewVersionOf] = useState("");
  const [meta, setMeta] = useState({
    title: "",
    country: "SG",
    business_unit: "Retail Banking",
    category: "Loans",
    product: "",
    access_group: user?.access_groups[0] ?? "",
    effective_date: new Date().toISOString().slice(0, 10),
    expiry_date: "",
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.documents().then((d) => setDocs(d.filter((x) => x.versions.some((v) => v.status === "ACTIVE")))).catch(() => undefined);
  }, []);

  function pickVersionOf(docId: string) {
    setNewVersionOf(docId);
    const d = docs.find((x) => x.doc_id === docId);
    if (d)
      setMeta((m) => ({
        ...m,
        title: d.title,
        business_unit: d.business_unit,
        category: d.category,
        product: d.product ?? "",
        access_group: d.access_group,
        country: d.country,
      }));
  }

  function choose(f: File | undefined) {
    if (!f) return;
    setFile(f);
    setResult(null);
    if (!meta.title && !newVersionOf) setMeta((m) => ({ ...m, title: f.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ") }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setResult(null);
    const form = new FormData();
    form.append("file", file);
    Object.entries(meta).forEach(([k, v]) => v && form.append(k, v));
    if (newVersionOf) form.append("doc_id", newVersionOf);
    try {
      const r = await api.upload(form);
      setResult({ kind: "ok", text: `Submitted "${meta.title}" v${r.version_no} for verification.`, conflict: r.conflict, versionNo: r.version_no });
      setFile(null);
      refreshStats();
    } catch (err) {
      const e2 = err as ApiError;
      setResult({ kind: e2.status === 409 ? "duplicate" : "error", text: e2.message });
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof typeof meta) => (e: { target: { value: string } }) => setMeta((m) => ({ ...m, [k]: e.target.value }));
  const locked = !!newVersionOf;

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-7">
      <PageHeader title="Upload document" subtitle="Submitted documents go to a Data Steward for verification, then Owner approval and Custodian acknowledgement." />
      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
        <div className="flex flex-col gap-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              choose(e.dataTransfer.files[0]);
            }}
            onClick={() => inputRef.current?.click()}
            className={`flex min-h-[230px] cursor-pointer flex-col items-center justify-center gap-2 rounded-[14px] border-2 border-dashed p-6 text-center transition-colors ${
              drag ? "border-accent bg-accent/5" : "border-border bg-surface hover:border-accent/40"
            }`}
          >
            <input ref={inputRef} type="file" accept="application/pdf" hidden onChange={(e) => choose(e.target.files?.[0])} />
            {file ? (
              <>
                <FilePdf size={40} weight="duotone" className="text-accent" />
                <div className="text-[14px] font-semibold">{file.name}</div>
                <div className="text-[12px] text-muted">{(file.size / 1024).toFixed(0)} KB · click to change</div>
              </>
            ) : (
              <>
                <CloudArrowUp size={40} weight="duotone" className="text-muted" />
                <div className="text-[14px] font-semibold">Drop a PDF here or click to browse</div>
                <div className="text-[12px] text-muted">PDF only in the POC · public or synthetic content</div>
              </>
            )}
          </div>

          <Card className="p-4">
            <Field label="New version of an existing document (optional)" hint="Leave empty for a new document. A new version supersedes the current one once approved.">
              <select value={newVersionOf} onChange={(e) => (e.target.value ? pickVersionOf(e.target.value) : setNewVersionOf(""))} className={inputClass}>
                <option value="">— New document —</option>
                {docs.map((d) => (
                  <option key={d.doc_id} value={d.doc_id}>
                    {d.title} (current v{Math.max(...d.versions.map((v) => v.version_no))})
                  </option>
                ))}
              </select>
            </Field>
          </Card>

          {result && <ResultPanel r={result} />}
        </div>

        <Card className="flex flex-col gap-4 p-5">
          <Field label="Title">
            <input required value={meta.title} onChange={set("title")} className={inputClass} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Country">
              <select value={meta.country} onChange={set("country")} className={inputClass} disabled={locked}>
                {["SG", "MY", "ID", "HK", "CN"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Business unit">
              <select value={meta.business_unit} onChange={set("business_unit")} className={inputClass} disabled={locked}>
                {UNITS.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Category">
              <select value={meta.category} onChange={set("category")} className={inputClass} disabled={locked}>
                {CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Product">
              <input value={meta.product} onChange={set("product")} placeholder="e.g. Home Loan" className={inputClass} disabled={locked} />
            </Field>
            <Field label="Access group">
              <select value={meta.access_group} onChange={set("access_group")} className={inputClass} disabled={locked}>
                {user?.access_groups.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </Field>
            <div />
            <Field label="Effective date">
              <input type="date" required value={meta.effective_date} onChange={set("effective_date")} className={inputClass} />
            </Field>
            <Field label="Expiry date (optional)">
              <input type="date" value={meta.expiry_date} onChange={set("expiry_date")} className={inputClass} />
            </Field>
          </div>
          <Button type="submit" variant="primary" loading={busy} disabled={!file} className="mt-2">
            <CloudArrowUp size={17} weight="bold" /> Submit for verification
          </Button>
        </Card>
      </form>
    </div>
  );
}

function ResultPanel({ r }: { r: Result }) {
  const near = r.conflict?.near_duplicates.filter((n) => n.flag === "near_duplicate") ?? [];
  const tone = r.kind === "ok" ? "bg-success/10 text-success" : r.kind === "duplicate" ? "bg-error/10 text-error" : "bg-error/10 text-error";
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={`rounded-[14px] p-4 text-[13px] ${tone}`}>
      <div className="flex items-start gap-2 font-semibold">
        {r.kind === "ok" ? <CheckCircle size={18} weight="fill" /> : <Prohibit size={18} weight="bold" />}
        <div>
          {r.kind === "duplicate" && <div className="mb-0.5 text-[11px] uppercase tracking-[0.06em]">Exact duplicate blocked</div>}
          {r.text}
        </div>
      </div>
      {near.length > 0 && (
        <div className="mt-2 flex items-start gap-2 rounded-lg bg-warning/10 p-2.5 text-warning">
          <Warning size={16} weight="fill" className="mt-0.5 shrink-0" />
          <div>
            Near-duplicate flagged for the steward:{" "}
            {near.map((n) => `"${n.title}" v${n.version_no} (${(n.similarity * 100).toFixed(1)}% similar)`).join(", ")}
          </div>
        </div>
      )}
    </motion.div>
  );
}
