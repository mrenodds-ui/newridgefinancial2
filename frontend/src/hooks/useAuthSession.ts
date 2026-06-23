import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { getApiAuthenticatedUsername, subscribeToApiAuthStateChange } from "../api/basicAuth";
import { fetchAuthSession } from "../api/client";
import { queryKeys } from "../queryClient";

type AuthSessionError = Error & {
  status?: number;
};

export function useAuthSession() {
  const authenticatedUsername = useSyncExternalStore(subscribeToApiAuthStateChange, getApiAuthenticatedUsername, () => null);
  const sessionQuery = useQuery({
    queryKey: queryKeys.authSession,
    queryFn: fetchAuthSession,
    retry: false,
    staleTime: 60_000,
  });

  const session = sessionQuery.isSuccess ? sessionQuery.data : null;
  const resolvedUsername = session?.username ?? authenticatedUsername;
  const roles = session?.roles ?? [];
  const isAuthenticated = Boolean(resolvedUsername);
  const isSessionAuthenticated = Boolean(session?.username);
  const isLoading = sessionQuery.isPending;
  const isError = isAuthenticated && sessionQuery.isError;
  const isRoleKnown = sessionQuery.isSuccess;
  const error = sessionQuery.error instanceof Error ? (sessionQuery.error as AuthSessionError) : null;

  return {
    authenticatedUsername: resolvedUsername,
    session,
    roles,
    isAuthenticated,
    isSessionAuthenticated,
    isSessionVerified: sessionQuery.isSuccess,
    isLoading,
    isError,
    isRoleKnown,
    error,
    sessionStatusCode: typeof error?.status === "number" ? error.status : null,
    isAdmin: sessionQuery.isSuccess && roles.includes("admin"),
    retry: sessionQuery.refetch,
  };
}