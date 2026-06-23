import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProviderProduction } from "../../types/dashboard";
import styles from "./ProviderPerformanceChart.module.css";

function getTrends(data: ProviderProduction[]) {
  // Dummy trend: compare first and last value for each provider
  return data.map((row) => ({
    ...row,
    trend: row.production - row.collections, // Example: positive if production > collections
  }));
}

function detectAnomaly(data: ProviderProduction[]) {
  // Example: alert if any provider has collections < 50% of production
  return data.some((row) => row.collections < 0.5 * row.production);
}

export function ProviderPerformanceChart({ data }: { data: ProviderProduction[] }) {
  const trendData = useMemo(() => getTrends(data), [data]);
  const anomaly = useMemo(() => detectAnomaly(data), [data]);
  return (
    <section className="dashboard-provider-performance">
      <h3 className="dashboard-section-title">Provider Performance (Chart)</h3>
      {anomaly && (
        <div className={styles["provider-anomaly"]}>⚠️ Anomaly detected: Some providers have collections less than 50% of production.</div>
      )}
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={trendData} margin={{ top: 16, right: 32, left: 0, bottom: 16 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="provider" />
          <YAxis />
          <Tooltip
            formatter={(value: number) =>
              value.toLocaleString("en-US", {
                style: "currency",
                currency: "USD",
              })
            }
          />
          <Legend />
          <Bar dataKey="production" fill="#2563eb" name="Production" />
          <Bar dataKey="collections" fill="#16a34a" name="Collections" />
          <Line type="monotone" dataKey="trend" stroke="#f59e42" name="Trend (Prod - Coll)" />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
