export interface StoragePersistenceResult {
  supported: boolean;
  persisted: boolean;
  granted: boolean;
}

export async function requestPersistentStorage(
  storageManager: StorageManager | undefined = globalThis.navigator?.storage,
): Promise<StoragePersistenceResult> {
  if (!storageManager?.persist || !storageManager.persisted) {
    return {
      supported: false,
      persisted: false,
      granted: false,
    };
  }

  try {
    const alreadyPersisted = await storageManager.persisted();
    if (alreadyPersisted) {
      return {
        supported: true,
        persisted: true,
        granted: true,
      };
    }

    const granted = await storageManager.persist();
    return {
      supported: true,
      persisted: granted,
      granted,
    };
  } catch {
    return {
      supported: true,
      persisted: false,
      granted: false,
    };
  }
}
