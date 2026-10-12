import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { EVENT_LABEL, SEVERITY_COLOR } from "../../utils";
import type { EventType } from "../../types/event";

/** Shared form-control look (use on <input>/<select>). */
export const inputCls =
  "mt-1.5 w-full rounded-[10px] border border-line bg-[#0c1330] px-3 py-2.5 text-sm text-ink outline-none " +
  "focus:border-brand focus:ring-4 focus:ring-brand/20";

export const labelCls = "block text-[12.5px] text-mute";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-11 text-center text-mute">
      <div className="size-7 animate-spin rounded-full border-[3px] border-line border-t-brand" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-11 text-center">
      <Inbox size={32} className="text-mute" />
      <strong>{title}</strong>
      {hint && <span className="text-mute">{hint}</span>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong";
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-11 text-center text-bad">
      <AlertTriangle size={32} />
      <strong>Couldn't load data</strong>
      <span className="text-mute">{message}</span>
      {onRetry && (
        <Button onClick={onRetry}>
          <RefreshCw size={14} /> Retry
        </Button>
      )}
    </div>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[10px] border border-bad/35 bg-bad/12 px-3 py-2 text-[12.5px] text-[#ffc0c9]">{children}</div>
  );
}

const variants = {
  default: "border-line bg-white/5 hover:bg-white/10",
  primary: "border-transparent bg-gradient-to-br from-brand to-[#5b6cf5] text-white shadow-lg shadow-brand/35 hover:brightness-110",
  danger: "border-bad/45 bg-bad/15 text-[#ffb4c0] hover:bg-bad/25",
  icon: "border-line bg-white/5 px-2.5 hover:bg-white/10 hover:text-bad",
} as const;

export function Button({ variant = "default", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof variants }) {
  return (
    <button
      {...props}
      className={`inline-flex cursor-pointer items-center gap-2 rounded-[11px] border px-4 py-2.5 text-[13.5px] font-medium transition
        enabled:hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    />
  );
}

const tones = {
  ok: "border-ok/40 bg-ok/10 text-ok",
  degraded: "border-warn/40 bg-white/5 text-warn",
  down: "border-bad/40 bg-bad/10 text-bad",
  idle: "border-line bg-white/5 text-ink",
} as const;
const dots = {
  ok: "bg-ok animate-[ping-ok_1.8s_infinite]",
  degraded: "bg-warn",
  down: "bg-bad",
  idle: "bg-mute",
} as const;

export function StatusPill({ tone, children }: { tone: keyof typeof tones; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-[7px] whitespace-nowrap rounded-full border px-[11px] py-[5px] text-xs font-semibold ${tones[tone]}`}>
      <span className={`size-2 rounded-full ${dots[tone]}`} />
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const c = SEVERITY_COLOR[severity] ?? "#94a3b8";
  return (
    <span className="rounded-full border px-[9px] py-[3px] text-[11px] font-bold tracking-wide"
      style={{ color: c, background: `${c}1f`, borderColor: `${c}55` }}>
      {severity}
    </span>
  );
}

export function EventTypeBadge({ type }: { type: EventType }) {
  return (
    <span className="whitespace-nowrap rounded-lg bg-brand/12 px-2.5 py-[3px] text-xs text-[#c3caff]">
      {EVENT_LABEL[type] ?? type}
    </span>
  );
}

export function Card({ title, action, children, className = "" }: {
  title?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-line bg-gradient-to-b from-[#172044]/75 to-panel/75 p-5 shadow-xl shadow-black/25 backdrop-blur ${className}`}>
      {(title || action) && (
        <header className="mb-3.5 flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">{title}</h3>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, icon, color, hint }: {
  label: string; value: ReactNode; icon: ReactNode; color: string; hint?: string;
}) {
  return (
    <div className="relative flex items-center gap-4 overflow-hidden rounded-2xl border border-line bg-gradient-to-b from-[#172044]/75 to-panel/75 p-5 shadow-xl shadow-black/25 backdrop-blur">
      <div aria-hidden className="absolute -right-8 -top-8 size-28 rounded-full opacity-[0.12] blur-sm" style={{ background: color }} />
      <div className="grid size-[50px] shrink-0 place-items-center rounded-[14px] border"
        style={{ color, background: `${color}29`, borderColor: `${color}59` }}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[13px] text-mute">{label}</div>
        <div className="text-[30px] font-bold leading-tight tracking-tight">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-mute">{hint}</div>}
      </div>
    </div>
  );
}
