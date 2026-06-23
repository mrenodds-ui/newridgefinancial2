import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

export const queryKeys = {
  authSession: ["auth-session"] as const,
  health: ["health"] as const,
  kpis: ["kpis"] as const,
  localKpiRecords: ["local-kpi-records"] as const,
  adminSummary: ["admin-summary"] as const,
  halStatus: ["hal-status"] as const,
  halAudits: ["hal-audits"] as const,
  importJobs: ["importJobs"] as const,
  queuedSyncCount: ["queued-sync-count"] as const,
};
