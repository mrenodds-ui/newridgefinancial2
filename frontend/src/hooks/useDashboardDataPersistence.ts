import { useEffect } from "react";
import { useDashboardData } from "../context/DashboardDataContext";
import { loadDashboardDataFromIndexedDB, saveDashboardDataToIndexedDB } from "../utils/indexedDbDashboard";

export function useDashboardDataPersistence() {
  const { dashboardData, setDashboardData } = useDashboardData();

  // Load from IndexedDB on mount
  useEffect(() => {
    void (async () => {
      const dbData = await loadDashboardDataFromIndexedDB();
      if (dbData) setDashboardData(dbData);
    })();
  }, [setDashboardData]);

  // Save to IndexedDB on change
  useEffect(() => {
    if (dashboardData && dashboardData.length > 0) {
      void saveDashboardDataToIndexedDB(dashboardData);
    }
  }, [dashboardData]);
}
