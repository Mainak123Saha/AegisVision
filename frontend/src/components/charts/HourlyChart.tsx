import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HourlyBucket } from "../../types/event";
import { EVENT_COLOR, EVENT_LABEL } from "../../utils";
import type { EventType } from "../../types/event";

const TYPES = Object.keys(EVENT_LABEL) as EventType[];

export const tooltipStyle = {
  contentStyle: { background: "#111936", border: "1px solid #2a3560", borderRadius: 10, color: "#e6e9f5" },
  labelStyle: { color: "#9aa4c7" },
};

export default function HourlyChart({ data, showDate }: { data: HourlyBucket[]; showDate?: boolean }) {
  const rows = data.map((b) => ({
    label: new Date(b.hour).toLocaleString(undefined, showDate
      ? { month: "short", day: "numeric", hour: "2-digit" }
      : { hour: "2-digit", minute: "2-digit" }),
    ...Object.fromEntries(TYPES.map((t) => [t, b.by_type[t] ?? 0])),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={rows} margin={{ top: 10, right: 12, left: -16, bottom: 0 }}>
        <defs>
          {TYPES.map((t) => (
            <linearGradient key={t} id={`g-${t}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={EVENT_COLOR[t]} stopOpacity={0.55} />
              <stop offset="95%" stopColor={EVENT_COLOR[t]} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke="#222c52" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" stroke="#6b7699" tick={{ fontSize: 11 }} minTickGap={24} />
        <YAxis stroke="#6b7699" tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {TYPES.map((t) => (
          <Area key={t} type="monotone" dataKey={t} name={EVENT_LABEL[t]} stackId="1"
            stroke={EVENT_COLOR[t]} strokeWidth={2} fill={`url(#g-${t})`} />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
