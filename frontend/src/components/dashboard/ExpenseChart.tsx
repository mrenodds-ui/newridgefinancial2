import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ExpenseCategory } from "../../types/dashboard";
import { ChartCard } from "./ChartCard";

const COLORS = ["#D6B15E", "#A9823A", "#B98B4B", "#D89A2B", "#78A86B", "#C96A5B"];

export function ExpenseChart({ data, title }: { data: ExpenseCategory[]; title: string }) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} layout="vertical" margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#3a2d1a" strokeDasharray="3 3" />
          <XAxis type="number" stroke="#B9AA91" tickFormatter={(v) => v.toLocaleString()} tick={{ fill: "#F7F0E2" }} />
          <YAxis dataKey="category" type="category" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} width={120} />
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
          <Bar dataKey="amount" barSize={28}>
            {data.map((entry, idx) => (
              <Cell key={entry.category} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
