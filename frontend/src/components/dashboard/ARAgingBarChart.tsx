import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency } from "../../../utils/formatting";

const AR_COLORS = ["#D6B15E", "#A9823A", "#D89A2B", "#C96A5B"];

export function ARAgingBarChart({ data, height = 320 }: { data: { name: string; value: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(214, 177, 94, 0.14)" strokeDasharray="3 3" />
        <XAxis dataKey="name" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} />
        <YAxis stroke="#B9AA91" tickFormatter={formatCurrency} tick={{ fill: "#F7F0E2" }} />
        <Tooltip
          contentStyle={{
            background: "#18120C",
            color: "#F7F0E2",
            borderRadius: 12,
            border: "1.5px solid #D6B15E",
          }}
          labelStyle={{ color: "#D6B15E" }}
          formatter={formatCurrency}
        />
        <Legend wrapperStyle={{ color: "#D6B15E" }} iconType="rect" />
        <Bar dataKey="value" isAnimationActive={false} barSize={38}>
          {data.map((entry, idx) => (
            <Cell key={entry.name} fill={AR_COLORS[idx % AR_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
