import type React from "react";
import { createContext, useContext, useState } from "react";

type DashboardDataRow = Record<string, unknown>;

export type DashboardDataContextType = {
  dashboardData: DashboardDataRow[];
  setDashboardData: (data: DashboardDataRow[]) => void;
};

const DashboardDataContext = createContext<DashboardDataContextType | undefined>(undefined);

export function useDashboardData() {
  const ctx = useContext(DashboardDataContext);
  if (!ctx) throw new Error("useDashboardData must be used within a DashboardDataProvider");
  return ctx;
}

export const DashboardDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dashboardData, setDashboardData] = useState<DashboardDataRow[]>([]);
  return <DashboardDataContext.Provider value={{ dashboardData, setDashboardData }}>{children}</DashboardDataContext.Provider>;
};
