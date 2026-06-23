const ADMIN_REFRESH_SYNC_TAG = "newridge-admin-refresh-retry";

type BackgroundSyncRegistration = ServiceWorkerRegistration & {
  sync: {
    register: (tag: string) => Promise<void>;
  };
};

export function supportsBackgroundSync(registration: ServiceWorkerRegistration | null): registration is BackgroundSyncRegistration {
  return Boolean(registration && typeof (registration as BackgroundSyncRegistration).sync?.register === "function");
}

export async function registerAdminRefreshBackgroundSync(registration: ServiceWorkerRegistration | null): Promise<boolean> {
  if (!supportsBackgroundSync(registration)) {
    return false;
  }

  try {
    await registration.sync.register(ADMIN_REFRESH_SYNC_TAG);
    return true;
  } catch {
    return false;
  }
}

export function getAdminRefreshSyncTag(): string {
  return ADMIN_REFRESH_SYNC_TAG;
}
