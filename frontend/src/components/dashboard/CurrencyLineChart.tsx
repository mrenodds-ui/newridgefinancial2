import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency, formatMonthLabel } from "../../../utils/formatting";

type ChartDatum = Record<string, string | number | null | undefined>;

export function CurrencyLineChart({
  data,
  lines,
  height = 320,
  legend = true,
}: {
  data: ChartDatum[];
  lines: { dataKey: string; name: string; color: string }[];
  height?: number;
  legend?: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(214, 177, 94, 0.14)" strokeDasharray="3 3" />
        <XAxis dataKey="date" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} tickFormatter={formatMonthLabel} />
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
          labelFormatter={formatMonthLabel}
        />
        {legend && <Legend wrapperStyle={{ color: "#D6B15E" }} iconType="circle" />}
        {lines.map((line) => (
          <Line
            key={line.dataKey}
            type="monotone"
            dataKey={line.dataKey}
            name={line.name}
            stroke={line.color}
            strokeWidth={3}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
