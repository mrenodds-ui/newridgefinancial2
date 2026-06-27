import { useEffect, useState } from "react";

import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";

const SETTINGS_STORAGE_KEY = "dashboardSettings";

type DashboardSettings = {
  practiceName: string;
  notifications: boolean;
  importSchedule: string;
};

type SettingsValidationErrors = {
  practiceName?: string;
  importSchedule?: string;
};

const DEFAULT_SETTINGS: DashboardSettings = {
  practiceName: "New Ridge Family Dental",
  notifications: false,
  importSchedule: "Daily",
};

function readStoredSettings(): DashboardSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }

  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_SETTINGS;
    }

    const parsed = JSON.parse(raw) as Partial<DashboardSettings>;
    return {
      practiceName: typeof parsed.practiceName === "string" ? parsed.practiceName : DEFAULT_SETTINGS.practiceName,
      notifications: typeof parsed.notifications === "boolean" ? parsed.notifications : DEFAULT_SETTINGS.notifications,
      importSchedule: typeof parsed.importSchedule === "string" ? parsed.importSchedule : DEFAULT_SETTINGS.importSchedule,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function validateSettings(settings: DashboardSettings): SettingsValidationErrors {
  const errors: SettingsValidationErrors = {};

  if (!settings.practiceName.trim()) {
    errors.practiceName = "Practice name is required.";
  } else if (settings.practiceName.trim().length > 80) {
    errors.practiceName = "Practice name must be 80 characters or fewer.";
  }

  if (!settings.importSchedule.trim()) {
    errors.importSchedule = "Import schedule is required.";
  } else if (settings.importSchedule.trim().length > 40) {
    errors.importSchedule = "Import schedule must be 40 characters or fewer.";
  }

  return errors;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<DashboardSettings>(() => readStoredSettings());
  const [persistedAt, setPersistedAt] = useState<string | null>(null);
  const validationErrors = validateSettings(settings);
  const hasValidationErrors = Boolean(validationErrors.practiceName || validationErrors.importSchedule);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    setPersistedAt(new Date().toISOString());
  }, [settings]);

  const persistedLabel = persistedAt
    ? new Date(persistedAt).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
    : "Not saved yet";

  function updateSetting<Key extends keyof DashboardSettings>(key: Key, value: DashboardSettings[Key]) {
    setSettings((current) => ({
      ...current,
      [key]: value,
    }));
  }

  return (
    <PageSurfaceShell className="settings-page">
      <PageSurfaceHeader
        breadcrumbs="Owner / Workspace settings"
        eyebrow="Workspace settings"
        title="Settings"
        titleId="settings-page-title"
        description="Practice profile, branding, and data settings. Changes save locally in this browser."
        badges={[
          { label: "Local Browser Storage" },
          { label: "No Cloud Sync" },
        ]}
      />
      <div className="page-state-card page-state-card--info settings-page__status" id="settings-save-status" role="status">
        {hasValidationErrors
          ? "Draft saved locally. Fix the highlighted fields before using these values elsewhere."
          : `Saved locally at ${persistedLabel}.`}
      </div>
      <div className="dashboard-settings-section">
        <h2>Practice Info</h2>
        <div className="settings-page__form">
          <label className="settings-page__field" htmlFor="settings-practice-name">
            <span>Practice Name</span>
            {validationErrors.practiceName ? (
              <input
                id="settings-practice-name"
                className="settings-page__input"
                value={settings.practiceName}
                onChange={(event) => updateSetting("practiceName", event.target.value)}
                maxLength={80}
                required
                aria-invalid="true"
                aria-describedby="settings-practice-name-error"
              />
            ) : (
              <input
                id="settings-practice-name"
                className="settings-page__input"
                value={settings.practiceName}
                onChange={(event) => updateSetting("practiceName", event.target.value)}
                maxLength={80}
                required
                aria-invalid="false"
                aria-describedby="settings-save-status"
              />
            )}
          </label>
          {validationErrors.practiceName ? (
            <p className="settings-page__error" id="settings-practice-name-error" role="alert">
              {validationErrors.practiceName}
            </p>
          ) : (
            <p className="settings-page__hint">Shown across local settings and mock practice profile surfaces.</p>
          )}
        </div>
      </div>
      <div className="dashboard-settings-section">
        <h2>Branding</h2>
        <div>
          Theme: <strong>New Ridge Family</strong>
        </div>
      </div>
      <div className="dashboard-settings-section">
        <h2>Data Sources</h2>
        <div>SoftDent, QuickBooks (mock only)</div>
      </div>
      <div className="dashboard-settings-section">
        <h2>Notifications</h2>
        <label className="settings-page__checkbox" htmlFor="settings-notifications">
          <input
            id="settings-notifications"
            type="checkbox"
            checked={settings.notifications}
            onChange={(event) => updateSetting("notifications", event.target.checked)}
          />
          <span>Enable notifications</span>
        </label>
      </div>
      <div className="dashboard-settings-section">
        <h2>Import Schedule</h2>
        <div className="settings-page__form">
          <label className="settings-page__field" htmlFor="settings-import-schedule">
            <span>Schedule</span>
            {validationErrors.importSchedule ? (
              <input
                id="settings-import-schedule"
                className="settings-page__input"
                value={settings.importSchedule}
                onChange={(event) => updateSetting("importSchedule", event.target.value)}
                maxLength={40}
                required
                aria-invalid="true"
                aria-describedby="settings-import-schedule-error"
              />
            ) : (
              <input
                id="settings-import-schedule"
                className="settings-page__input"
                value={settings.importSchedule}
                onChange={(event) => updateSetting("importSchedule", event.target.value)}
                maxLength={40}
                required
                aria-invalid="false"
                aria-describedby="settings-save-status"
              />
            )}
          </label>
          {validationErrors.importSchedule ? (
            <p className="settings-page__error" id="settings-import-schedule-error" role="alert">
              {validationErrors.importSchedule}
            </p>
          ) : (
            <p className="settings-page__hint">Examples: Daily, Weekdays at 6:00 AM, or Manual only.</p>
          )}
        </div>
      </div>
      <div className="dashboard-settings-section">
        <h2>Support</h2>
        <div>
          Email: <a href="mailto:support@newridgefamily.com">support@newridgefamily.com</a>
        </div>
      </div>
    </PageSurfaceShell>
  );
}
