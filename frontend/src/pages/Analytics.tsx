import { Activity, DoorOpen, Hourglass, ShieldAlert } from "lucide-react";
import { useState } from "react";
import BreakdownChart from "../components/charts/BreakdownChart";
import HourlyChart from "../components/charts/HourlyChart";
import { Card, EmptyState, ErrorState, Spinner, StatCard } from "../components/common/ui";
import { useCameras, useHoursAgo, useHourly, useSummary } from "../hooks/queries";
import type { EventType } from "../types/event";
import { EVENT_COLOR, EVENT_LABEL, SEVERITY_COLOR } from "../utils";

const RANGES = [
  { label: "24 hours", hours: 24 },
  { label: "7 days", hours: 24 * 7 },
  { label: "30 days", hours: 24 * 30 },
];

export default function Analytics() {
  const [hours, setHours] = useState(24);
  const start = useHoursAgo(hours);
  const summary = useSummary(start);
  const hourly = useHourly(start);
  const cameras = useCameras();
  const s = summary.data;
  const names = new Map((cameras.data ?? []).map((c) => [String(c.id), c.name]));

  const typeSlices = Object.entries(s?.by_type ?? {}).map(([k, v]) => ({
    name: EVENT_LABEL[k as EventType] ?? k, value: v, color: EVENT_COLOR[k as EventType] ?? "#94a3b8",
  }));
  const sevSlices = Object.entries(s?.by_severity ?? {}).map(([k, v]) => ({
    name: k, value: v, color: SEVERITY_COLOR[k] ?? "#94a3b8",
  }));
  const perCamera = Object.entries(s?.by_camera ?? {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...perCamera.map(([, v]) => v));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-xl border border-line bg-white/5 p-1">
          {RANGES.map((r) => (
            <button key={r.hours} onClick={() => setHours(r.hours)}
              className={`cursor-pointer rounded-[9px] px-4 py-[7px] text-[13px] font-medium transition ${
                hours === r.hours ? "bg-gradient-to-br from-brand to-[#5b6cf5] text-white" : "text-mute hover:text-ink"}`}>
              {r.label}
            </button>
          ))}
        </div>
        <span className="text-[12.5px] text-mute">Last {RANGES.find((r) => r.hours === hours)?.label}</span>
      </div>

      {summary.isError && <ErrorState error={summary.error} onRetry={() => summary.refetch()} />}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-5">
        <StatCard label="Total events" color="#818cf8" icon={<Activity size={22} />} value={summary.isLoading ? "…" : s?.total_events ?? "–"} />
        <StatCard label="Intrusions" color="#fb7185" icon={<ShieldAlert size={22} />} value={summary.isLoading ? "…" : s?.intrusion_events ?? "–"} />
        <StatCard label="Loitering" color="#fbbf24" icon={<Hourglass size={22} />} value={summary.isLoading ? "…" : s?.loitering_events ?? "–"} />
        <StatCard label="Line crossings" color="#38bdf8" icon={<DoorOpen size={22} />} value={summary.isLoading ? "…" : s?.line_crossed_events ?? "–"}
          hint={s ? `${s.visitors_in} in · ${s.visitors_out} out` : undefined} />
      </div>

      <Card title="Hourly trend">
        {hourly.isLoading ? <Spinner /> : hourly.isError ? <ErrorState error={hourly.error} onRetry={() => hourly.refetch()} />
          : !s?.total_events ? <EmptyState title="No events in this period" />
          : <HourlyChart data={hourly.data ?? []} showDate={hours > 24} />}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Incident types">
          {summary.isLoading ? <Spinner /> : !typeSlices.length ? <EmptyState title="No data" /> : <BreakdownChart data={typeSlices} />}
        </Card>
        <Card title="Severity breakdown">
          {summary.isLoading ? <Spinner /> : !sevSlices.length ? <EmptyState title="No data" /> : <BreakdownChart data={sevSlices} />}
        </Card>
      </div>

      <Card title="Events by camera">
        {summary.isLoading ? <Spinner /> : !perCamera.length ? <EmptyState title="No data" /> : (
          <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
            {perCamera.map(([id, v]) => (
              <li key={id} className="grid grid-cols-[180px_1fr_50px] items-center gap-3.5 max-sm:grid-cols-[110px_1fr_40px]">
                <span className="truncate">{names.get(id) ?? (id === "unassigned" ? "Deleted / unassigned" : `Camera ${id}`)}</span>
                <div className="h-2.5 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand to-sky2 transition-[width] duration-500" style={{ width: `${(v / max) * 100}%` }} />
                </div>
                <strong className="text-right">{v}</strong>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
