type DashboardExportRow = Record<string, unknown>;

export function useDashboardExport(data: DashboardExportRow[], filename = "dashboard-data.csv") {
  function exportToCSV() {
    if (!data || !data.length) return;
    const keys = Object.keys(data[0]);
    const csvRows = [keys.join(",")];
    for (const row of data) {
      csvRows.push(keys.map((k) => JSON.stringify(row[k] ?? "")).join(","));
    }
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return { exportToCSV };
}
