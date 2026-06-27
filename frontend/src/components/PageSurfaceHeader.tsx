import type { ReactNode } from "react";

import "../styles/page-surface.css";

type PageSurfaceBadge = {
  label: string;
  tone?: "neutral" | "warning";
};

type PageSurfaceStatusItem = {
  label: string;
  value: string;
};

export function PageSurfaceHeader({
  breadcrumbs,
  eyebrow,
  title,
  titleId,
  description,
  badges,
  statusItems,
  badgesAriaLabel = "Page safety posture",
  statusAriaLabel = "Page source status",
}: {
  breadcrumbs: string;
  eyebrow: string;
  title: string;
  titleId: string;
  description: ReactNode;
  badges: readonly PageSurfaceBadge[];
  statusItems?: readonly PageSurfaceStatusItem[];
  badgesAriaLabel?: string;
  statusAriaLabel?: string;
}) {
  return (
    <header className="page-surface__hero" aria-labelledby={titleId}>
      <div className="page-surface__hero-top">
        <div className="page-surface__hero-copy">
          <div className="page-surface__breadcrumbs">{breadcrumbs}</div>
          <p className="eyebrow">{eyebrow}</p>
          <h1 id={titleId}>{title}</h1>
          {typeof description === "string" ? <p className="dashboard-description">{description}</p> : description}
        </div>
        <div className="page-surface__badges" aria-label={badgesAriaLabel}>
          {badges.map((badge) => (
            <span
              key={badge.label}
              className={[
                "page-surface__badge",
                badge.tone === "warning" ? "page-surface__badge--warning" : "page-surface__badge--neutral",
              ].join(" ")}
            >
              {badge.label}
            </span>
          ))}
        </div>
      </div>
      {statusItems?.length ? (
        <div className="page-surface__status-strip" aria-label={statusAriaLabel}>
          {statusItems.map((item) => (
            <div key={item.label} className="page-surface__status-item">
              <span className="page-surface__status-label">{item.label}</span>
              <span className="page-surface__status-value">{item.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </header>
  );
}

export function PageSurfaceShell({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={["dashboard-page page-surface", className].filter(Boolean).join(" ")}>{children}</div>;
}
