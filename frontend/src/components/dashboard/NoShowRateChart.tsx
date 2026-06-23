import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function NoShowRateChart({ data }: { data: { date: string; noShowRate: number }[] }) {
  return (
    <section className="dashboard-no-show-rate">
      <h3 className="dashboard-section-title">No-Show Rate Trend</h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 16, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#D6B15E33" />
          <XAxis dataKey="date" stroke="#B9AA91" tick={{ fontSize: 13, fill: "#F7F0E2" }} />
          <YAxis stroke="#B9AA91" tickFormatter={(v) => `${v}%`} tick={{ fill: "#F7F0E2" }} />
          <Tooltip
            contentStyle={{
              background: "#18120C",
              color: "#F7F0E2",
              borderRadius: 12,
              border: "1.5px solid #D6B15E",
            }}
            labelStyle={{ color: "#D6B15E" }}
            formatter={(v: number) => `${v}%`}
          />
          <Line type="monotone" dataKey="noShowRate" stroke="#C96A5B" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}
