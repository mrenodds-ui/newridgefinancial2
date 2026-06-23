// IndexedDB utility for dashboard data persistence
// Uses idb-keyval for simplicity (install with: npm install idb-keyval)
import { del, get, set, update } from "idb-keyval";

const DASHBOARD_DB_KEY = "dashboard-data";

export type DashboardDataStore = Record<string, unknown>[];

export async function saveDashboardDataToIndexedDB(data: DashboardDataStore) {
  await set(DASHBOARD_DB_KEY, data);
}

export async function loadDashboardDataFromIndexedDB() {
  return await get<DashboardDataStore>(DASHBOARD_DB_KEY);
}

export async function clearDashboardDataFromIndexedDB() {
  await del(DASHBOARD_DB_KEY);
}

export async function updateDashboardDataInIndexedDB(updater: (data: DashboardDataStore | undefined) => DashboardDataStore) {
  await update<DashboardDataStore>(DASHBOARD_DB_KEY, updater);
}
