import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { chooseBrowserBackupFile, exportBrowserBackup, importBrowserBackupFile } from "../browser/browserBackup";
import { supportsFileSystemAccess } from "../browser/fileAccess";
import { queryKeys } from "../queryClient";

import styles from "./BrowserBackupCard.module.css";
import { DashboardCard } from "./DashboardCard";

export function BrowserBackupCard(): JSX.Element {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const fileSystemAccessSupported = supportsFileSystemAccess();

  const exportMutation = useMutation({
    mutationFn: async () => {
      await exportBrowserBackup();
    },
  });

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      await importBrowserBackupFile(file);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.kpis });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminSummary });
      void queryClient.invalidateQueries({ queryKey: queryKeys.importJobs });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health });
    },
  });

  const handleImportClick = async () => {
    const selectedFile = await chooseBrowserBackupFile(window);
    if (selectedFile) {
      void importMutation.mutateAsync(selectedFile);
      return;
    }
    fileInputRef.current?.click();
  };

  return (
    <DashboardCard title="Local Backup / Restore" accent="slate">
      <div className={styles["browser-backup-card-grid"]}>
        <p className={styles["browser-backup-card-p"]}>
          Export or restore browser-side IndexedDB data. File System Access is used when available; upload/download is the fallback.
        </p>
        <p className={styles["browser-backup-card-p-secondary"]}>
          Before major updates, export a backup snapshot so local-only edits can be restored if needed.
        </p>
        <div className={styles["browser-backup-card-flex"]}>
          <button type="button" onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending}>
            {exportMutation.isPending ? "Exporting..." : "Export Backup"}
          </button>
          <button type="button" onClick={() => void handleImportClick()} disabled={importMutation.isPending}>
            {importMutation.isPending ? "Importing..." : "Import Backup"}
          </button>
        </div>
        <label htmlFor="browser-backup-file-input" className={styles.hiddenInput}>
          Import backup file
        </label>
        <input
          id="browser-backup-file-input"
          ref={fileInputRef}
          type="file"
          accept="application/json"
          className={styles.hiddenInput}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              void importMutation.mutateAsync(file);
            }
            event.currentTarget.value = "";
          }}
          aria-label="Import backup file"
        />
        <p className={styles["browser-backup-card-p-tertiary"]}>
          File System Access: {fileSystemAccessSupported ? "available" : "unavailable"}
        </p>
      </div>
    </DashboardCard>
  );
}
