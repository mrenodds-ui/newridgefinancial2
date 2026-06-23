import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrendPoint } from "../../types/dashboard";
import { ChartCard } from "./ChartCard";

export function TrendChart({
  data,
  title,
  dataKey,
  color,
}: {
  data: TrendPoint[];
  title: string;
  dataKey: keyof TrendPoint;
  color: string;
}) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#3a2d1a" strokeDasharray="3 3" />
          <XAxis dataKey="date" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} />
          <YAxis stroke="#B9AA91" tickFormatter={(v) => v.toLocaleString()} tick={{ fill: "#F7F0E2" }} />
          <Tooltip
            contentStyle={{
              background: "#18120C",
              color: "#F7F0E2",
              borderRadius: 12,
              border: "1.5px solid #D6B15E",
            }}
            labelStyle={{ color: "#D6B15E" }}
          />
          <Legend wrapperStyle={{ color: "#D6B15E" }} iconType="circle" />
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
