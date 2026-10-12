import type { Camera } from "../../types/camera";
import type { EventItem } from "../../types/event";
import { eventSummary, formatDateTime, formatStreamTime } from "../../utils";
import { EventTypeBadge, SeverityBadge } from "../common/ui";

const th = "border-b border-line px-3 py-2.5 text-left text-[11.5px] font-semibold uppercase tracking-wider text-mute";
const td = "border-b border-line/60 px-3 py-[13px]";

export default function EventsTable({ events, cameras }: { events: EventItem[]; cameras: Camera[] | undefined }) {
  const names = new Map((cameras ?? []).map((c) => [c.id, c.name]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13.5px]">
        <thead>
          <tr>
            <th className={th}>Time</th><th className={th}>Type</th><th className={th}>Details</th><th className={th}>Severity</th><th className={th}>Camera</th><th className={th}>Track</th><th className={th}>Video time</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.event_id} className="transition hover:bg-brand/6">
              <td className={td + " whitespace-nowrap"}>{formatDateTime(e.created_at)}</td>
              <td className={td}><EventTypeBadge type={e.event_type} /></td>
              <td className={td}>{eventSummary(e.event_type, e.metadata)}</td>
              <td className={td}><SeverityBadge severity={e.severity} /></td>
              <td className={td}>{e.camera_id === null ? <span className="text-mute">deleted</span> : names.get(e.camera_id) ?? `#${e.camera_id}`}</td>
              <td className={td + " font-mono text-[12.5px]"}>#{e.track_id}</td>
              <td className={td + " font-mono text-[12.5px]"}>{formatStreamTime(e.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
