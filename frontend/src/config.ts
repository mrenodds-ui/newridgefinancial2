/**
 * Centralized app config.
 *
 * All Vite define constants and import.meta.env accesses are funneled through
 * this module. Components and modules import from here — never from
 * import.meta.env or the __CONSTANT__ globals directly.
 *
 * The Zod parse at module load time fails fast at startup if the build
 * tooling omitted a required constant.
 */
import { z } from "zod";

const configSchema = z.object({
  /** API base path. All fetch calls are relative to this. */
  apiBaseUrl: z.string().min(1),
  /** App version from package.json, injected at build time. */
  appVersion: z.string().min(1),
  /** ISO build timestamp, injected at build time. */
  buildDate: z.string().min(1),
  /** Git commit SHA (7-char short), injected at build time. Falls back to "dev". */
  commitHash: z.string().min(1),
  /** True when running the Vite dev server. */
  isDev: z.boolean(),
});

export type AppConfig = z.infer<typeof configSchema>;

function loadConfig(): AppConfig {
  // All config is injected at build time by Vite define or import.meta.env
  const raw = {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
    appVersion: import.meta.env.VITE_APP_VERSION || __APP_VERSION__,
    buildDate: import.meta.env.VITE_BUILD_DATE || __BUILD_DATE__,
    commitHash: import.meta.env.VITE_COMMIT_HASH || __COMMIT_HASH__,
    isDev: import.meta.env.DEV === true,
  };

  const result = configSchema.safeParse(raw);
  if (!result.success) {
    // Throw synchronously so the app never reaches the render cycle with
    // missing or invalid build metadata.
    throw new Error(`App config is invalid — the build is likely misconfigured.\n${result.error.toString()}`);
  }

  return result.data;
}

export const config: AppConfig = loadConfig();
