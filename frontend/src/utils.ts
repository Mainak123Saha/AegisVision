import type { EventType } from "./types/event";

export const EVENT_LABEL: Record<EventType, string> = {
  LINE_CROSSED: "Line crossing",
  INTRUSION_DETECTED: "Intrusion",
  LOITERING: "Loitering",
};

export const EVENT_COLOR: Record<EventType, string> = {
  LINE_CROSSED: "#38bdf8",
  INTRUSION_DETECTED: "#fb7185",
  LOITERING: "#fbbf24",
};

export const SEVERITY_COLOR: Record<string, string> = {
  INFO: "#38bdf8",
  WARNING: "#fbbf24",
  CRITICAL: "#fb7185",
};

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function formatTimeAgo(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/** Stream seconds -> m:ss */
export function formatStreamTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function eventSummary(type: EventType, md: Record<string, unknown>): string {
  if (type === "LINE_CROSSED") return `Crossed ${md.line_id ?? "line"} (${md.direction ?? "?"})`;
  if (type === "INTRUSION_DETECTED") return `Entered ${md.zone_name ?? md.zone_id ?? "restricted zone"}`;
  const d = typeof md.duration === "number" ? ` for ${Math.round(md.duration)}s` : "";
  return `Loitering in ${md.zone_name ?? md.zone_id ?? "zone"}${d}`;
}
