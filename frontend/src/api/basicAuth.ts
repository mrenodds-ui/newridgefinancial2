type ApiAuthRequiredDetail = {
  invalidCredentials: boolean;
};

const API_AUTH_REQUIRED_EVENT = "api-auth-required";
const API_AUTH_STATE_CHANGED_EVENT = "api-auth-state-changed";
const authEventTarget = new EventTarget();

let currentUsername: string | null = null;

function notifyApiAuthStateChanged(): void {
  authEventTarget.dispatchEvent(new Event(API_AUTH_STATE_CHANGED_EVENT));
}

function encodeBase64Utf8(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  if (typeof globalThis.btoa === "function") {
    return globalThis.btoa(binary);
  }
  throw new Error("Base64 encoding is unavailable in this runtime.");
}

export function createBasicAuthorizationHeader(username: string, password: string): string {
  return `Basic ${encodeBase64Utf8(`${username}:${password}`)}`;
}

export function getApiAuthorizationHeader(): string | null {
  return null;
}

export function getApiAuthenticatedUsername(): string | null {
  return currentUsername;
}

export function setApiAuthenticatedUsername(username: string | null): void {
  const normalizedUsername = username?.trim() || null;
  if (currentUsername === normalizedUsername) {
    return;
  }
  currentUsername = normalizedUsername;
  notifyApiAuthStateChanged();
}

export function setApiBasicAuthCredentials(username: string, password: string): void {
  void password;
  setApiAuthenticatedUsername(username);
}

export function clearApiBasicAuthCredentials(): void {
  setApiAuthenticatedUsername(null);
}

export function notifyApiAuthRequired(invalidCredentials: boolean): void {
  if (invalidCredentials) {
    clearApiBasicAuthCredentials();
  }
  authEventTarget.dispatchEvent(
    new CustomEvent<ApiAuthRequiredDetail>(API_AUTH_REQUIRED_EVENT, {
      detail: { invalidCredentials },
    }),
  );
}

export function subscribeToApiAuthRequired(callback: (detail: ApiAuthRequiredDetail) => void): () => void {
  const listener: EventListener = (event) => {
    callback((event as CustomEvent<ApiAuthRequiredDetail>).detail);
  };
  authEventTarget.addEventListener(API_AUTH_REQUIRED_EVENT, listener);
  return () => authEventTarget.removeEventListener(API_AUTH_REQUIRED_EVENT, listener);
}

export function subscribeToApiAuthStateChange(callback: () => void): () => void {
  const listener: EventListener = () => {
    callback();
  };
  authEventTarget.addEventListener(API_AUTH_STATE_CHANGED_EVENT, listener);
  return () => authEventTarget.removeEventListener(API_AUTH_STATE_CHANGED_EVENT, listener);
}
