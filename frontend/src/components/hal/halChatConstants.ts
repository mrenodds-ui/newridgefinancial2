export const HAL_CHAT_ALLOWED_ROLES = new Set(["dashboard:read", "hal:operator"]);

export const HAL_MOCK_ASSISTANT_RESPONSE =
  "HAL chat UI is active in frontend-only mode. Backend AI connection is not configured yet. Once connected, I can help explain dashboard numbers, summarize reports, draft internal follow-up tasks, and assist with office-manager workflows.";

export const HAL_GREETING_TITLE = "Hi, I'm HAL";

export const HAL_GREETING_SUBTITLE =
  "Your internal office assistant for read, draft, and explain workflows inside New Ridge Family Financial.";

export const HAL_SAFETY_BOUNDARIES = [
  "Read / draft / local-only by default",
  "No SoftDent writeback",
  "No claim submission",
  "No faxing",
  "No emailing",
  "No uploading",
  "No external action",
] as const;

export const HAL_FRONTEND_ONLY_NOTE = "Frontend-only mode: messages stay in this browser session until a backend assistant is connected.";

export const HAL_BACKEND_NOTE = "Backend mode: HAL uses the browser API and local Ollama when available. External actions remain blocked.";

export function halRuntimeNote(): string {
  return import.meta.env.VITE_HAL_CHAT_MODE === "mock" ? HAL_FRONTEND_ONLY_NOTE : HAL_BACKEND_NOTE;
}

export function isHalMockChatMode(): boolean {
  return import.meta.env.VITE_HAL_CHAT_MODE === "mock";
}
