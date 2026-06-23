export function downloadSampleFile() {
  const sample = [
    ["provider", "production", "collections"],
    ["Dr. Smith", 10000, 9000],
    ["Dr. Lee", 8000, 7500],
    ["Dr. Patel", 12000, 11000],
  ];
  const csv = sample.map((row) => row.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sample-dashboard-data.csv";
  a.click();
  URL.revokeObjectURL(url);
}
