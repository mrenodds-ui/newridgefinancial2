import { useCallback, useEffect, useState } from "react";

// Sample/mock data builders (replace with real logic as needed)
function buildSummary() {
  return { total: 10000, patients: 120, updated: new Date().toISOString() };
}
function buildTrends() {
  return [
    { date: "2024-01", value: 1000 },
    { date: "2024-02", value: 1200 },
    { date: "2024-03", value: 1100 },
  ];
}
function buildExpenses() {
  return [
    { date: "2024-01", value: 400 },
    { date: "2024-02", value: 500 },
    { date: "2024-03", value: 450 },
  ];
}
function buildARAging() {
  return [
    { name: "0–30", value: 3000 },
    { name: "31–60", value: 2000 },
    { name: "61–90", value: 1000 },
    { name: "90+", value: 500 },
  ];
}
function buildImportHistory() {
  return [
    { date: "2024-03-01", status: "Success" },
    { date: "2024-02-01", status: "Success" },
  ];
}

export function useDashboardData() {
  const [summary, setSummary] = useState(() => buildSummary());
  const [trends, setTrends] = useState(() => buildTrends());
  const [expenses, setExpenses] = useState(() => buildExpenses());
  const [arAging, setArAging] = useState(() => buildARAging());
  const [importHistory, setImportHistory] = useState(() => buildImportHistory());
  const [lastRefreshedAt, setLastRefreshedAt] = useState(() => new Date());
  const [refreshing, setRefreshing] = useState(false);

  // Central refresh function
  const refreshDashboard = useCallback(() => {
    setRefreshing(true);
    // Simulate data rebuild (replace with real logic or IndexedDB as needed)
    setSummary({ ...buildSummary() });
    setTrends([...buildTrends()]);
    setExpenses([...buildExpenses()]);
    setArAging([...buildARAging()]);
    setImportHistory([...buildImportHistory()]);
    setLastRefreshedAt(new Date());
    setTimeout(() => setRefreshing(false), 800); // Show indicator briefly
    // Temporary debug logs
    console.log("Dashboard refreshed", new Date().toISOString());
    console.log("Trend points", buildTrends().length);
  }, []);

  // 30-minute auto-refresh
  useEffect(() => {
    const intervalId = window.setInterval(() => {
      refreshDashboard();
    }, 1800000); // 30 min
    return () => window.clearInterval(intervalId);
  }, [refreshDashboard]);

  return {
    summary,
    trends,
    expenses,
    arAging,
    importHistory,
    lastRefreshedAt,
    refreshing,
    refreshDashboard,
  };
}
