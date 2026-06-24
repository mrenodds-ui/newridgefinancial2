export function downloadSampleFile() {
  const sample = [
    ["provider", "production", "collections"],
    ["Entire Practice", 135000, 126500],
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
