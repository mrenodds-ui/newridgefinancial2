import type { ReactNode } from "react";

export function SummaryCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="dashboard-summary-card">
      <h3 className="dashboard-summary-card__title">{title}</h3>
      <div className="dashboard-summary-card__content">{children}</div>
    </section>
  );
}
