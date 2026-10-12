import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { tooltipStyle } from "./HourlyChart";

export interface Slice { name: string; value: number; color: string }

export default function BreakdownChart({ data }: { data: Slice[] }) {
  const total = data.reduce((a, b) => a + b.value, 0);
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={68} outerRadius={98} paddingAngle={3} stroke="none">
            {data.map((s) => <Cell key={s.name} fill={s.color} />)}
          </Pie>
          <Tooltip {...tooltipStyle} itemStyle={{ color: "#e6e9f5" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-x-0 top-0 bottom-[34px] flex flex-col items-center justify-center">
        <strong className="text-[26px]">{total}</strong>
        <span className="text-xs text-mute">events</span>
      </div>
    </div>
  );
}
