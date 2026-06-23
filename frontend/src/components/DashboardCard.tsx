import type { ReactNode } from "react";

type DashboardCardProps = {
  title: string;
  children: ReactNode;
  accent?: "gold" | "green" | "rust" | "slate";
};

export function DashboardCard({ title, children, accent = "slate" }: DashboardCardProps): JSX.Element {
  const accentClass = `dashboard-card--${accent}`;
  return (
    <section className={`dashboard-card ${accentClass}`}>
      <h3 className="dashboard-card__title">{title}</h3>
      {children}
    </section>
  );
}
