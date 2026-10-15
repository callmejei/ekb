import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-white shadow-[0_2px_8px_rgba(224,48,42,0.22)] hover:bg-[#c42822] hover:-translate-y-px disabled:opacity-45",
  secondary: "border border-border bg-surface text-text hover:bg-surface-2 disabled:opacity-40",
  ghost: "bg-transparent text-muted hover:bg-surface-2 hover:text-text disabled:opacity-40",
  danger: "border border-error/60 bg-transparent text-error hover:bg-error/10 disabled:opacity-40",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      disabled={disabled || loading}
      className={`tap inline-flex cursor-pointer items-center justify-center gap-2 rounded-[10px] font-semibold transition-all duration-150 disabled:cursor-not-allowed ${
        size === "sm" ? "h-8 px-3 text-[12px]" : "h-10 px-4 text-[13px]"
      } ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {loading && <Spinner size={13} />}
      {children}
    </button>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent opacity-80"
      style={{ width: size, height: size }}
    />
  );
}

export function Badge({ children, tone = "muted", className = "" }: { children: ReactNode; tone?: Tone; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-bold tracking-[0.03em] ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export type Tone = "muted" | "accent" | "success" | "warning" | "error" | "info" | "graph";

const TONES: Record<Tone, string> = {
  muted: "bg-muted/15 text-muted",
  accent: "bg-accent/12 text-accent",
  success: "bg-success/12 text-success",
  warning: "bg-warning/14 text-warning",
  error: "bg-error/12 text-error",
  info: "bg-info/12 text-info",
  graph: "bg-graph/14 text-graph",
};

export const STATUS_TONE: Record<string, Tone> = {
  ACTIVE: "success",
  SUBMITTED: "info",
  VERIFIED: "info",
  APPROVED: "info",
  ACKNOWLEDGED: "warning",
  SUPERSEDED: "muted",
  REJECTED: "error",
  RETURNED: "warning",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "muted"}>{status}</Badge>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[14px] border border-border bg-surface ${className}`}>{children}</div>;
}

export function Empty({ icon, title, body }: { icon: ReactNode; title: string; body?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-2 text-muted">{icon}</div>
      <div className="text-[15px] font-semibold">{title}</div>
      {body && <div className="max-w-md text-[13px] text-muted">{body}</div>}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">{label}</span>
      {children}
      {hint && <span className="text-[12px] text-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "h-10 w-full rounded-lg border border-border bg-input-bg px-3 text-[13px] text-text outline-none transition-colors placeholder:text-muted/70 hover:border-accent/30 focus:border-accent focus:ring-3 focus:ring-accent/15";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[22px] font-extrabold tracking-[-0.02em]">{title}</h1>
        {subtitle && <p className="mt-1 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function fmtDate(s: string | null | undefined) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(s: string) {
  return new Date(s).toLocaleString("en-SG", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
