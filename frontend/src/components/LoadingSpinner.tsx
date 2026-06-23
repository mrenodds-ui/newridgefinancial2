import "./LoadingSpinner.css";

export function LoadingSpinner({ label = "Loading…" }: { label?: string }): JSX.Element {
  return (
    <div aria-live="polite" aria-label={label} className="loading-spinner">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" className="loading-spinner__icon">
        <g>
          <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeDasharray="40 12" />
        </g>
      </svg>
      <span className="loading-spinner__label">{label}</span>
    </div>
  );
}
