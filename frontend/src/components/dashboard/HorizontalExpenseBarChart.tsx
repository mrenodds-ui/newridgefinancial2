import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency } from "../../../utils/formatting";

const COLORS = ["#D6B15E", "#A9823A", "#B98B4B", "#D89A2B", "#78A86B", "#C96A5B"];

type HorizontalExpenseBarDatum = {
  category: string;
  amount: number;
};

export function HorizontalExpenseBarChart({ data, height = 320 }: { data: HorizontalExpenseBarDatum[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(214, 177, 94, 0.14)" strokeDasharray="3 3" />
        <XAxis type="number" stroke="#B9AA91" tickFormatter={formatCurrency} tick={{ fill: "#F7F0E2" }} />
        <YAxis dataKey="category" type="category" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} width={120} />
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
        <Bar dataKey="amount" barSize={28}>
          {data.map((entry, idx) => (
            <Cell key={entry.category} fill={COLORS[idx % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
