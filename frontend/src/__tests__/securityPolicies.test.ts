import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = path.resolve(process.cwd(), "src");

async function listSourceFiles(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const nested = await Promise.all(
    entries
      .filter((entry) => entry.name !== "__tests__")
      .map((entry) => {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          return listSourceFiles(fullPath);
        }
        if (/\.(ts|tsx)$/.test(entry.name)) {
          return [fullPath];
        }
        return [];
      }),
  );

  return nested.flat();
}

describe("frontend security policies", () => {
  it("does not store app secrets in local/session storage", async () => {
    const files = await listSourceFiles(SRC_DIR);
    const sensitiveStoragePattern =
      /(localStorage|sessionStorage)\.(getItem|setItem)\([^\n]*(token|secret|password|auth|cookie|session|bearer|api[-_]?key)/i;

    for (const filePath of files) {
      const contents = await readFile(filePath, "utf8");
      expect(contents).not.toMatch(sensitiveStoragePattern);
    }
  });

  it("avoids dangerouslySetInnerHTML in source components", async () => {
    const files = await listSourceFiles(SRC_DIR);

    for (const filePath of files) {
      const contents = await readFile(filePath, "utf8");
      expect(contents).not.toContain("dangerouslySetInnerHTML");
    }
  });
});
