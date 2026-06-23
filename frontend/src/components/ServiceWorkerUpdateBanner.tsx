import "./feedback-surfaces.css";

type ServiceWorkerUpdateBannerProps = {
  onRefresh: () => void;
};

export function ServiceWorkerUpdateBanner({ onRefresh }: ServiceWorkerUpdateBannerProps): JSX.Element | null {
  return (
    <section aria-live="polite" className="service-worker-update-banner">
      <div className="service-worker-update-banner__content">
        <strong className="service-worker-update-banner__title">New version available</strong>
        <span className="service-worker-update-banner__message">Refresh to activate the latest browser shell.</span>
      </div>
      <button type="button" onClick={onRefresh} className="service-worker-update-banner__action">
        Refresh now
      </button>
    </section>
  );
}
