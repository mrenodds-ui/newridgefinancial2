export async function withWebLock<T>(
  name: string,
  task: () => Promise<T> | T,
  lockManager: LockManager | undefined = globalThis.navigator?.locks,
): Promise<T> {
  if (!lockManager?.request) {
    return Promise.resolve(task());
  }

  return lockManager.request(name, { mode: "exclusive" }, task);
}
