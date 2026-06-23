import "./feedback-surfaces.css";

interface EmptyStateProps {
  title?: string;
  message?: string;
  /** Optional label for the action button */
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ title = "No data", message, actionLabel, onAction }: EmptyStateProps): JSX.Element {
  let icon = null;
  const lowerTitle = title.toLowerCase();
  if (lowerTitle.includes("denied")) {
    icon = (
      <span role="img" aria-label="denied">
        ⛔
      </span>
    );
  } else if (lowerTitle.includes("offline")) {
    icon = (
      <span role="img" aria-label="offline">
        📴
      </span>
    );
  } else if (lowerTitle.includes("stale")) {
    icon = (
      <span role="img" aria-label="stale">
        🕒
      </span>
    );
  } else if (lowerTitle.includes("success")) {
    icon = (
      <span role="img" aria-label="success">
        ✅
      </span>
    );
  }
  return (
    <div aria-live="polite" className="empty-state">
      {icon ? (
        <span className="empty-state__icon">{icon}</span>
      ) : (
        <svg className="empty-state__fallback-icon" aria-hidden="true" width="40" height="40" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" />
          <path d="M13 20h14M20 13v14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.35" />
        </svg>
      )}
      <strong className="empty-state__title">{title}</strong>
      {message ? <p className="empty-state__message">{message}</p> : null}
      {actionLabel && onAction ? (
        <button type="button" onClick={onAction} className="empty-state__action">
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
