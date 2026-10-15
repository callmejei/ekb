/**
 * App shell: left navigation rail (Prism pattern — icons collapsed, labels when expanded, sliding
 * active marker) and a top bar with the signed-in identity, access groups and theme toggle.
 */

import { useState, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { NavLink, useLocation } from "react-router-dom";
import {
  Books,
  CaretDoubleLeft,
  CaretDoubleRight,
  ChatCircleText,
  CheckSquareOffset,
  Moon,
  ShieldCheck,
  SignOut,
  Sun,
  UploadSimple,
  type Icon,
} from "@phosphor-icons/react";
import { ROLE_LABEL, useSession } from "../session";

const SPRING = { type: "spring" as const, stiffness: 210, damping: 26, mass: 0.6 };

interface Item {
  to: string;
  label: string;
  icon: Icon;
  show: (roles: string[]) => boolean;
  badge?: "tasks";
}

const ITEMS: Item[] = [
  { to: "/ask", label: "Ask", icon: ChatCircleText, show: () => true },
  { to: "/library", label: "Library", icon: Books, show: () => true },
  { to: "/upload", label: "Upload", icon: UploadSimple, show: (r) => r.includes("REQUESTOR") || r.includes("ADMIN") },
  {
    to: "/tasks",
    label: "Approvals",
    icon: CheckSquareOffset,
    show: (r) => ["STEWARD", "OWNER", "CUSTODIAN", "ADMIN"].some((x) => r.includes(x)),
    badge: "tasks",
  },
  { to: "/audit", label: "Audit trail", icon: ShieldCheck, show: (r) => r.includes("ADMIN") },
];

export const TITLES: Record<string, string> = {
  "/ask": "Ask the knowledge base",
  "/library": "Library",
  "/upload": "Upload document",
  "/tasks": "Approvals",
  "/audit": "Audit trail",
};

export function Shell({ children }: { children: ReactNode }) {
  const { user, stats, signOut, theme, toggleTheme } = useSession();
  const [open, setOpen] = useState(true);
  const reduce = useReducedMotion();
  const location = useLocation();
  if (!user) return null;
  const items = ITEMS.filter((i) => i.show(user.roles));
  const width = open ? 232 : 64;

  return (
    <div className="flex h-dvh overflow-hidden bg-bg text-text">
      <motion.aside
        animate={{ width }}
        transition={reduce ? { duration: 0 } : SPRING}
        className="flex shrink-0 flex-col overflow-hidden border-r border-border bg-surface"
        aria-label="Main navigation"
      >
        <div className="flex h-[64px] shrink-0 items-center border-b border-border px-3.5">
          {open ? (
            <motion.img
              key="wordmark"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              src={theme === "dark" ? "/ocbc-knowledge-dark.png" : "/ocbc-knowledge-light.png"}
              alt="OCBC Knowledge"
              className="h-10 w-auto"
            />
          ) : (
            <img src="/ocbc-emblem.png" alt="OCBC Knowledge" className="h-9 w-9" />
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-2">
          {items.map((item) => {
            const active = location.pathname.startsWith(item.to);
            const Icon = item.icon;
            const count = item.badge === "tasks" ? stats?.pending_tasks ?? 0 : 0;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                title={open ? undefined : item.label}
                className={`relative flex h-10 shrink-0 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors ${
                  active ? "text-accent" : "text-muted hover:bg-surface-2 hover:text-text"
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    transition={reduce ? { duration: 0 } : SPRING}
                    className="absolute inset-0 -z-0 rounded-lg bg-accent/10"
                  />
                )}
                <Icon size={19} weight={active ? "fill" : "regular"} className="relative shrink-0" />
                {open && <span className="relative whitespace-nowrap">{item.label}</span>}
                {count > 0 && (
                  <span
                    className={`relative ml-auto rounded-full bg-accent px-1.5 text-[10.5px] font-bold leading-[18px] text-white ${
                      open ? "" : "absolute top-1 right-1 ml-0"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-border p-2">
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex h-9 w-full cursor-pointer items-center gap-3 rounded-lg px-3 text-[12.5px] text-muted hover:bg-surface-2 hover:text-text"
            aria-label={open ? "Collapse navigation" : "Expand navigation"}
          >
            {open ? <CaretDoubleLeft size={16} /> : <CaretDoubleRight size={16} />}
            {open && <span className="whitespace-nowrap">Collapse</span>}
          </button>
        </div>
      </motion.aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[64px] shrink-0 items-center gap-4 border-b border-border bg-surface px-6 shadow-[0_1px_0_var(--c-border)]">
          <h2 className="truncate text-[15px] font-bold">{TITLES[location.pathname] ?? ""}</h2>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden items-center gap-1.5 md:flex">
              {user.access_groups.map((g) => (
                <span key={g} className="rounded-md border border-border px-2 py-0.5 font-mono text-[10.5px] text-muted">
                  {g}
                </span>
              ))}
            </div>
            <button
              onClick={toggleTheme}
              className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-border text-muted hover:border-accent hover:text-accent"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <div className="flex items-center gap-2.5 rounded-full border border-border py-1 pr-1 pl-3">
              <div className="text-right leading-tight">
                <div className="text-[12.5px] font-semibold">{user.display_name}</div>
                <div className="text-[10.5px] text-muted">{user.roles.map((r) => ROLE_LABEL[r] ?? r).join(", ")}</div>
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-[12px] font-bold text-accent">
                {user.display_name
                  .split(" ")
                  .map((p) => p[0])
                  .join("")
                  .slice(0, 2)}
              </div>
              <button
                onClick={signOut}
                title="Switch user"
                aria-label="Switch user"
                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-muted hover:bg-surface-2 hover:text-accent"
              >
                <SignOut size={16} />
              </button>
            </div>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
