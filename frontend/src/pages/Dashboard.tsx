import { Activity, DoorOpen, ShieldAlert, Users, Video } from "lucide-react";
import { Link } from "react-router-dom";
import HourlyChart from "../components/charts/HourlyChart";
import { Card, EmptyState, ErrorState, EventTypeBadge, SeverityBadge, Spinner, StatCard, StatusPill } from "../components/common/ui";
import { useCameraStatuses, useCameras, useEvents, useHourly, useSummary, useTodayStart } from "../hooks/queries";
import { eventSummary, formatTimeAgo } from "../utils";

const listCls = "m-0 flex list-none flex-col p-0";
const rowCls = "flex items-center gap-3 border-b border-line/70 px-1 py-3 last:border-b-0";
const linkCls = "text-[13px] font-medium text-brand hover:underline";

export default function Dashboard() {
  const today = useTodayStart();
  const cameras = useCameras();
  const statuses = useCameraStatuses(cameras.data);
  const summary = useSummary(today);
  const hourly = useHourly(today);
  const recent = useEvents({ limit: 8 });

  const names = new Map((cameras.data ?? []).map((c) => [c.id, c.name]));
  const running = Object.values(statuses).filter((s) => s?.running).length;
  const s = summary.data;
  const dash = (v: number | undefined) => (summary.isLoading ? "…" : summary.isError ? "–" : v ?? 0);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-5">
        <StatCard label="Cameras monitoring" color="#34d399" icon={<Video size={22} />}
          value={cameras.isLoading ? "…" : cameras.isError ? "–" : `${running} / ${cameras.data?.length ?? 0}`}
          hint="running right now" />
        <StatCard label="Events today" color="#818cf8" icon={<Activity size={22} />} value={dash(s?.total_events)}
          hint={s ? `${s.line_crossed_events} crossings · ${s.loitering_events} loitering` : undefined} />
        <StatCard label="Intrusion alerts" color="#fb7185" icon={<ShieldAlert size={22} />} value={dash(s?.intrusion_events)}
          hint="restricted-zone entries today" />
        <StatCard label="Visitors today" color="#38bdf8" icon={<Users size={22} />} value={dash(s?.visitors_in)}
          hint={s ? `${s.visitors_out} left · line crossings` : undefined} />
      </div>
      {summary.isError && <ErrorState error={summary.error} onRetry={() => summary.refetch()} />}

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <Card title="Events per hour · today">
          {hourly.isLoading ? <Spinner /> : hourly.isError ? <ErrorState error={hourly.error} onRetry={() => hourly.refetch()} />
            : s?.total_events === 0 ? <EmptyState title="No events yet today" hint="Start a camera to generate events." />
            : <HourlyChart data={hourly.data ?? []} />}
        </Card>

        <Card title="Camera status" action={<Link to="/cameras" className={linkCls}>Manage</Link>}>
          {cameras.isLoading ? <Spinner /> : cameras.isError ? <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />
            : !cameras.data?.length ? <EmptyState title="No cameras" hint="Add one on the Cameras page." />
            : <ul className={listCls}>
                {cameras.data.map((c) => {
                  const st = statuses[c.id];
                  const on = st?.running;
                  return (
                    <li key={c.id} className={rowCls}>
                      <StatusPill tone={on ? "ok" : st?.last_error ? "down" : "idle"}>{on ? "Live" : st?.last_error ? "Failed" : "Stopped"}</StatusPill>
                      <div className="min-w-0 flex-1"><strong>{c.name}</strong><div className="text-[12.5px] text-mute">{c.location || c.source_type.toUpperCase()}</div></div>
                      <span className="text-[12.5px] text-mute">{st?.events_persisted ?? 0} ev</span>
                    </li>
                  );
                })}
              </ul>}
        </Card>

        <Card title="Latest events" action={<Link to="/events" className={linkCls}>View all</Link>} className="lg:col-span-2">
          {recent.isLoading ? <Spinner /> : recent.isError ? <ErrorState error={recent.error} onRetry={() => recent.refetch()} />
            : !recent.data?.items.length ? <EmptyState title="No events recorded" hint="Events appear here once a camera detects activity." />
            : <ul className={listCls}>
                {recent.data.items.map((e) => (
                  <li key={e.event_id} className={rowCls}>
                    <SeverityBadge severity={e.severity} />
                    <div className="min-w-0 flex-1">
                      <strong>{eventSummary(e.event_type, e.metadata)}</strong>
                      <div className="text-[12.5px] text-mute">Track #{e.track_id} · {e.camera_id === null ? "deleted camera" : names.get(e.camera_id) ?? `Camera ${e.camera_id}`}</div>
                    </div>
                    <EventTypeBadge type={e.event_type} />
                    <span className="whitespace-nowrap text-[12.5px] text-mute">{formatTimeAgo(e.created_at)}</span>
                  </li>
                ))}
              </ul>}
        </Card>
      </div>
      <p className="flex items-center gap-1 text-[12.5px] text-mute"><DoorOpen size={12} /> Visitor counts are line-crossing events in the “IN” direction; they are only as accurate as the tracker.</p>
    </div>
  );
}
