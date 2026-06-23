import type { ReactNode } from "react";

import { useAuthSession } from "../hooks/useAuthSession";

type RequireApiAuthProps = {
  children: ReactNode;
  resourceName: string;
  requiredRoles?: readonly string[];
};

function buildRoleLabel(requiredRoles: readonly string[]) {
  return requiredRoles.join(", ");
}

export default function RequireApiAuth({ children, resourceName, requiredRoles = [] }: RequireApiAuthProps) {
  const { error, isLoading, isSessionVerified, roles, sessionStatusCode } = useAuthSession();

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <div className="page-content">
          <div className="page-state-card page-state-card--info" role="status">
            Verifying your dashboard session to load {resourceName}.
          </div>
        </div>
      </div>
    );
  }

  if (!isSessionVerified) {
    if (sessionStatusCode === 403) {
      return (
        <div className="dashboard-page">
          <div className="page-content">
            <div className="page-state-card page-state-card--error" role="alert">
              Your account is signed in, but it is not authorized to load {resourceName}.
            </div>
          </div>
        </div>
      );
    }

    if (error && sessionStatusCode !== 401) {
      return (
        <div className="dashboard-page">
          <div className="page-content">
            <div className="page-state-card page-state-card--error" role="alert">
              The dashboard session could not be verified right now. {error.message}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="dashboard-page">
        <div className="page-content">
          <div className="page-state-card page-state-card--info" role="status">
            Sign in from the dashboard banner to load {resourceName}.
          </div>
        </div>
      </div>
    );
  }

  const missingRequiredRole = requiredRoles.some((role) => !roles.includes(role));

  if (missingRequiredRole) {
    return (
      <div className="dashboard-page">
        <div className="page-content">
          <div className="page-state-card page-state-card--error" role="alert">
            Your account is signed in, but it is not authorized to load {resourceName}. Required role: {buildRoleLabel(requiredRoles)}.
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}