import { useEffect, useState } from "react";
import "./feedback-surfaces.css";

/**
 * Shows a banner when the browser reports the network is offline.
 * Disappears automatically when the connection is restored.
 */
export function OfflineBanner(): JSX.Element | null {
  const [offline, setOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div aria-live="polite" className="offline-banner">
      <svg className="offline-banner__icon" aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zm0 3.5v3m0 2v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      You are offline — data is from local cache.
    </div>
  );
}
