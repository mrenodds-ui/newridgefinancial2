export function backupDashboard() {
  const allKeys = Object.keys(localStorage).filter(
    (k) => k.startsWith("default::") || k.startsWith("doctor::") || k.startsWith("manager::") || k.startsWith("custom::"),
  );
  const backup: Record<string, string | null> = {};
  for (const key of allKeys) {
    backup[key] = localStorage.getItem(key);
  }
  const blob = new Blob([JSON.stringify(backup, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "dashboard-backup.json";
  a.click();
  URL.revokeObjectURL(url);
}

export function restoreDashboard(file: File, cb: (success: boolean) => void) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result as string) as Record<string, string | null>;
      for (const [key, value] of Object.entries(data)) {
        if (value === null) {
          localStorage.removeItem(key);
        } else {
          localStorage.setItem(key, value);
        }
      }
      cb(true);
    } catch {
      cb(false);
    }
  };
  reader.readAsText(file);
}
