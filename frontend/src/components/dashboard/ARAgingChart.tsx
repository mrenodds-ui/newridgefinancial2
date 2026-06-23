import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "./ChartCard";

export function ARAgingChart({
  ar0to30,
  ar31to60,
  ar61to90,
  arOver90,
}: {
  ar0to30: number;
  ar31to60: number;
  ar61to90: number;
  arOver90: number;
}) {
  const data = [
    { name: "0–30", value: ar0to30, color: "#D6B15E" },
    { name: "31–60", value: ar31to60, color: "#A9823A" },
    { name: "61–90", value: ar61to90, color: "#D89A2B" },
    { name: "90+", value: arOver90, color: "#C96A5B" },
  ];
  return (
    <ChartCard title="A/R Aging">
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#3a2d1a" strokeDasharray="3 3" />
          <XAxis dataKey="name" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} />
          <YAxis stroke="#B9AA91" tickFormatter={(v) => v.toLocaleString()} tick={{ fill: "#F7F0E2" }} />
          <Tooltip
            contentStyle={{
              background: "#18120C",
              color: "#F7F0E2",
              borderRadius: 12,
              border: "1.5px solid #D6B15E",
            }}
            labelStyle={{ color: "#D6B15E" }}
            formatter={(v) => `$${v.toLocaleString()}`}
          />
          <Legend wrapperStyle={{ color: "#D6B15E" }} iconType="rect" />
          <Bar dataKey="value" isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
