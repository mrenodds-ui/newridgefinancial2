type BrowserFileAccessScope = Window &
  typeof globalThis & {
    showSaveFilePicker?: (options?: {
      suggestedName?: string;
      types?: Array<{ description?: string; accept: Record<string, string[]> }>;
    }) => Promise<{
      createWritable(): Promise<{
        write(contents: string): Promise<void>;
        close(): Promise<void>;
      }>;
    }>;
    showOpenFilePicker?: (options?: {
      multiple?: boolean;
      types?: Array<{ description?: string; accept: Record<string, string[]> }>;
    }) => Promise<Array<{ getFile(): Promise<File> }>>;
  };

export interface SaveTextFileOptions {
  fileName: string;
  contents: string;
  mimeType?: string;
  globalScope?: BrowserFileAccessScope;
  documentRef?: Document;
}

export interface OpenTextFileOptions {
  mimeType?: string;
  globalScope?: BrowserFileAccessScope;
}

export function supportsFileSystemAccess(globalScope: BrowserFileAccessScope = globalThis as BrowserFileAccessScope): boolean {
  return typeof globalScope.showSaveFilePicker === "function" || typeof globalScope.showOpenFilePicker === "function";
}

export async function saveTextFile(options: SaveTextFileOptions): Promise<"file-system-access" | "download"> {
  const globalScope = options.globalScope ?? (globalThis as BrowserFileAccessScope);
  const documentRef = options.documentRef ?? globalThis.document;
  const mimeType = options.mimeType ?? "application/json";
  const saveFilePicker = globalScope.showSaveFilePicker;

  if (typeof saveFilePicker === "function") {
    const handle = await saveFilePicker({
      suggestedName: options.fileName,
      types: [{ description: "Backup file", accept: { [mimeType]: [".json"] } }],
    });
    const writable = await handle.createWritable();
    await writable.write(options.contents);
    await writable.close();
    return "file-system-access";
  }

  if (!documentRef?.createElement) {
    throw new Error("Cannot download file in this environment.");
  }

  const blob = new Blob([options.contents], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = documentRef.createElement("a");
  anchor.href = url;
  anchor.download = options.fileName;
  anchor.rel = "noopener";
  anchor.style.display = "none";
  documentRef.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return "download";
}

export async function openTextFile(options: OpenTextFileOptions = {}): Promise<File | null> {
  const globalScope = options.globalScope ?? (globalThis as BrowserFileAccessScope);
  const openFilePicker = globalScope.showOpenFilePicker;
  if (typeof openFilePicker !== "function") {
    return null;
  }

  const [handle] = await openFilePicker({
    multiple: false,
    types: [
      {
        description: "Backup file",
        accept: { [options.mimeType ?? "application/json"]: [".json"] },
      },
    ],
  });
  return handle ? handle.getFile() : null;
}
