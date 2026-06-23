import type React from "react";

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function ChartCard({ title, children, style }: ChartCardProps) {
  return (
    <section className="dashboard-chart-card" style={style}>
      <div className="dashboard-chart-title">{title}</div>
      {children}
    </section>
  );
}
