export interface ServiceWorkerRegistrationResult {
  supported: boolean;
  updateAvailable: boolean;
  waitingWorker: ServiceWorker | null;
  registration: ServiceWorkerRegistration | null;
}

export async function registerServiceWorker(
  onUpdateAvailable?: (registration: ServiceWorkerRegistration) => void,
): Promise<ServiceWorkerRegistrationResult> {
  if (!("serviceWorker" in navigator)) {
    return {
      supported: false,
      updateAvailable: false,
      waitingWorker: null,
      registration: null,
    };
  }

  const registration = await navigator.serviceWorker.register("/sw.js");
  let updateAvailable = false;

  const notifyUpdate = () => {
    updateAvailable = true;
    onUpdateAvailable?.(registration);
  };

  if (registration.waiting) {
    notifyUpdate();
  }

  registration.addEventListener("updatefound", () => {
    const installing = registration.installing;
    if (!installing) return;

    installing.addEventListener("statechange", () => {
      if (installing.state === "installed" && navigator.serviceWorker.controller) {
        notifyUpdate();
      }
    });
  });

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    window.location.reload();
  });

  return {
    supported: true,
    updateAvailable,
    waitingWorker: registration.waiting,
    registration,
  };
}

export function activateWaitingServiceWorker(registration: ServiceWorkerRegistration | null): boolean {
  if (!registration?.waiting) {
    return false;
  }
  registration.waiting.postMessage({ type: "SKIP_WAITING" });
  return true;
}
