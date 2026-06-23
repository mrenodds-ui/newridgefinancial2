import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  subscribeToApiAuthRequired,
} from "../api/basicAuth";
import { logoutAuthSession, verifyApiBasicAuthCredentials } from "../api/client";
import { useAuthSession } from "../hooks/useAuthSession";
import { queryKeys } from "../queryClient";
import Sidebar from "./Sidebar";
import "../theme.css";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { authenticatedUsername, error, isSessionAuthenticated, isSessionVerified, session, sessionStatusCode } = useAuthSession();
  const [authPromptOpen, setAuthPromptOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const hasCachedIdentity = Boolean(authenticatedUsername);
  const hasVerifiedSession = isSessionAuthenticated;
  const isVerificationPending = hasCachedIdentity && !isSessionVerified && !error;
  const hasVerificationError = hasCachedIdentity && !isSessionVerified && Boolean(error) && sessionStatusCode !== 401;
  const bannerClassName = hasVerifiedSession ? "api-auth-banner api-auth-banner--connected" : "api-auth-banner";
  const bannerTitle = hasVerifiedSession
    ? `Connected as ${session?.username}`
    : isVerificationPending
      ? "Verifying session..."
      : hasVerificationError
        ? "Session verification unavailable"
        : "Sign in required";
  const bannerMessage = hasVerifiedSession
    ? "Your dashboard session is managed by the backend and stays active until you sign out or it expires."
    : isVerificationPending
      ? "Checking the current backend-managed dashboard session before showing connected account details."
      : hasVerificationError
        ? "The current dashboard session could not be verified right now. Reconnect or try again after the session check recovers."
        : "Sign in with your dashboard account to load live HAL, SoftDent, QuickBooks, and document-library data.";
  const showSignOutButton = hasVerifiedSession || hasCachedIdentity;
  const primaryActionLabel = hasVerifiedSession || hasCachedIdentity ? "Switch account" : "Sign in";

  useEffect(() => {
    return subscribeToApiAuthRequired(({ invalidCredentials }) => {
      setPassword("");
      setAuthPromptOpen(true);
      setAuthError(
        invalidCredentials
          ? "Your dashboard session was rejected. Sign in again to continue."
          : "Sign in to load live HAL, SoftDent, QuickBooks, and document-library data.",
      );
    });
  }, []);

  async function handleAuthenticate(event: React.FormEvent) {
    event.preventDefault();
    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password) {
      setAuthError("Enter both a username and password.");
      return;
    }

    setIsAuthenticating(true);
    setAuthError(null);
    try {
      await verifyApiBasicAuthCredentials(normalizedUsername, password);
      setPassword("");
      setAuthPromptOpen(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.authSession });
      await queryClient.resetQueries();
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Unable to authenticate against the local API.");
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleSignOut() {
    await logoutAuthSession();
    setPassword("");
    setAuthPromptOpen(false);
    setAuthError(null);
    await queryClient.resetQueries();
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Sidebar />
      </aside>
      <main className="app-main">
        <div className="page-content">
          <section className={bannerClassName}>
            <div>
              <strong>{bannerTitle}</strong>
              <div>{bannerMessage}</div>
            </div>
            <div className="hal-form__actions">
              <button
                type="button"
                onClick={() => {
                  setAuthPromptOpen(true);
                  setAuthError(null);
                }}
              >
                {primaryActionLabel}
              </button>
              {showSignOutButton ? (
                <button type="button" onClick={() => void handleSignOut()}>
                  Sign out
                </button>
              ) : null}
            </div>
          </section>
          {children}
        </div>
      </main>
      {authPromptOpen ? (
        <div className="api-auth-modal-backdrop" role="presentation">
          <dialog className="api-auth-modal" aria-labelledby="api-auth-title" open>
            <h2 id="api-auth-title">Sign in to New Ridge Dashboard</h2>
            <p>
              Sign in once to start a backend-managed dashboard session. The browser uses that session cookie for the unified app after login.
            </p>
            <form className="hal-form hal-form--narrative" onSubmit={(event) => void handleAuthenticate(event)}>
              <label htmlFor="api-auth-username">Username</label>
              <input
                id="api-auth-username"
                className="hal-form__textarea"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
              <label htmlFor="api-auth-password">Password</label>
              <input
                id="api-auth-password"
                className="hal-form__textarea"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {authError ? <div className="api-auth-modal__error">{authError}</div> : null}
              <div className="hal-form__actions">
                <button type="submit" disabled={isAuthenticating}>
                  {isAuthenticating ? "Signing in..." : "Sign in"}
                </button>
                <button type="button" onClick={() => setAuthPromptOpen(false)} disabled={isAuthenticating}>
                  Cancel
                </button>
              </div>
            </form>
          </dialog>
        </div>
      ) : null}
    </div>
  );
}
