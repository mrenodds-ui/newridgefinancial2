/**
 * Centralized, typed feature flags for the New Ridge Financial Browser App.
 *
 * All feature flag reads must go through this module. Never scatter
 * import.meta.env or window checks in components. Add new flags here only.
 *
 * For simple cases, flags are derived from build-time config or URL params.
 * Add server-driven flags only if a feature genuinely needs staged rollout
 * or remote kill-switch control.
 */
import { config } from "./config";

export interface FeatureFlags {
  // ...existing code...
  /** Show the recovery panel when ?recovery=1 is in the URL. */
  readonly recoveryPanel: boolean;
  /**
   * Enable admin-only routes and controls.
   * Currently always enabled; access is controlled by routing.
   * To add role-based access, gate here (e.g., check user role from config or server).
   */
  readonly adminDashboard: boolean;
  /** Show Storybook-related dev tooling. Dev-only. */
  readonly storybookTooling: boolean;
}

function resolveFlags(): FeatureFlags {
  const search = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();

  return {
    // ...existing code...
    recoveryPanel: search.has("recovery"),
    // Admin dashboard is always enabled — access is controlled by URL routing.
    // If role-based access is added, gate it here.
    adminDashboard: true,
    storybookTooling: config.isDev,
  };
}

/**
 * Resolved at module load time. Flags derived from URL params are read once at load.
 * All feature flag logic is centralized here for maintainability and safety.
 */
export const featureFlags: FeatureFlags = resolveFlags();
