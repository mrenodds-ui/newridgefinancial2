import React from "react";

export function CaseAcceptanceFunnel({ presented, accepted }: { presented: number; accepted: number }) {
  const percent = presented > 0 ? Math.round((accepted / presented) * 100) : 0;
  return (
    <section className="dashboard-case-acceptance">
      <h3 className="dashboard-section-title">Case Acceptance Funnel</h3>
      <div className="case-acceptance-funnel">
        <div className="case-acceptance-row">
          <span className="case-acceptance-label">Treatment Plans Presented:</span>
          <span className="case-acceptance-value">{presented}</span>
        </div>
        <div className="case-acceptance-row">
          <span className="case-acceptance-label">Accepted:</span>
          <span className="case-acceptance-value">{accepted}</span>
        </div>
        <div className="case-acceptance-row">
          <span className="case-acceptance-label">Acceptance Rate:</span>
          <span className="case-acceptance-value">{percent}%</span>
        </div>
      </div>
    </section>
  );
}
