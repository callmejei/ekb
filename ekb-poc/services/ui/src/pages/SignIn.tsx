import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, LockKey } from "@phosphor-icons/react";
import { api, type User } from "../api";
import { ROLE_LABEL, useSession } from "../session";
import { Spinner } from "../components/ui";

const ROLE_HINT: Record<string, string> = {
  REQUESTOR: "Uploads documents and metadata",
  STEWARD: "Verifies content and metadata",
  OWNER: "Approves documents for use",
  CUSTODIAN: "Acknowledges and takes custody",
  VIEWER: "Asks questions; retail products only",
  ADMIN: "Sees the audit trail",
};

export default function SignIn() {
  const { signIn, theme } = useSession();
  const [users, setUsers] = useState<User[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.users().then(setUsers).catch((e) => setError(String(e.message ?? e)));
  }, []);

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-bg px-4 py-10">
      <div className="pointer-events-none absolute -top-40 -left-40 h-[520px] w-[520px] rounded-full bg-accent/10 blur-[120px]" />
      <div className="pointer-events-none absolute -right-40 -bottom-40 h-[480px] w-[480px] rounded-full bg-info/8 blur-[120px]" />

      <div className="relative grid w-full max-w-[1040px] items-center gap-12 md:grid-cols-[1fr_1.05fr]">
        <div>
          <div className="mb-7">
            <img
              src={theme === "dark" ? "/ocbc-knowledge-dark.png" : "/ocbc-knowledge-light.png"}
              alt="OCBC Knowledge"
              className="h-16 w-auto"
            />
            <div className="mt-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">
              Enterprise knowledge base · Proof of concept
            </div>
          </div>
          <h1 className="text-[34px] leading-[1.1] font-extrabold tracking-[-0.03em]">
            Governed documents.
            <br />
            <span className="text-accent">Answers you can cite.</span>
          </h1>
          <p className="mt-4 max-w-md text-[14px] text-muted">
            Every document enters through maker-checker approval, is indexed for hybrid search and a knowledge graph,
            and every answer cites the document, version and page — trimmed to what you are allowed to see.
          </p>
          <div className="mt-6 grid max-w-md grid-cols-3 gap-3 text-[12px]">
            {[
              ["Maker-checker", "4-step approval"],
              ["Hybrid + graph", "Elasticsearch · Neo4j"],
              ["Security trimmed", "per access group"],
            ].map(([a, b]) => (
              <div key={a} className="rounded-xl border border-border bg-surface/60 p-3">
                <div className="font-semibold">{a}</div>
                <div className="text-muted">{b}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[20px] border border-border bg-surface p-6 shadow-[var(--shadow-diffuse)]">
          <div className="mb-1 flex items-center gap-2 text-[15px] font-bold">
            <LockKey size={18} className="text-accent" /> Sign in as
          </div>
          <p className="mb-4 text-[12.5px] text-muted">Local demo identities. Production uses the bank's identity provider.</p>
          {error && <div className="rounded-lg bg-error/10 p-3 text-[13px] text-error">{error}</div>}
          {!users && !error && (
            <div className="flex justify-center py-10 text-muted">
              <Spinner />
            </div>
          )}
          <div className="flex flex-col gap-2">
            {users?.map((u, i) => (
              <motion.button
                key={u.username}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                disabled={!!busy}
                onClick={async () => {
                  setBusy(u.username);
                  try {
                    await signIn(u.username);
                  } catch (e) {
                    setError(String((e as Error).message));
                    setBusy(null);
                  }
                }}
                className="tap group flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-left transition-colors hover:border-accent/40"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent/12 text-[12px] font-bold text-accent">
                  {u.display_name
                    .split(" ")
                    .map((p) => p[0])
                    .join("")
                    .slice(0, 2)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[13.5px] font-semibold">{u.display_name}</span>
                    <span className="text-[11.5px] text-muted">{u.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</span>
                  </div>
                  <div className="truncate text-[11.5px] text-muted">
                    {ROLE_HINT[u.roles[0]]} · <span className="font-mono">{u.access_groups.join(", ")}</span>
                  </div>
                </div>
                {busy === u.username ? (
                  <Spinner size={14} />
                ) : (
                  <ArrowRight size={16} className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
                )}
              </motion.button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
