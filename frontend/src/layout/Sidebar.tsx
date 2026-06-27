import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

import { useAuthSession } from "../hooks/useAuthSession";

type NavItem = {
  label: string;
  path: string;
  requiresAdmin?: boolean;
};

type NavGroup = {
  label: string;
  items: NavItem[];
  muted?: boolean;
};

const navGroups: NavGroup[] = [
  {
    label: "Office",
    items: [
      { label: "Command Center", path: "/dashboard/hal" },
      { label: "Claims", path: "/claims-workbench" },
      { label: "Narratives", path: "/insurance-narratives" },
      { label: "Documents", path: "/accounting-documents" },
      { label: "Library", path: "/document-library" },
      { label: "Ask HAL", path: "/dashboard/hal" },
    ],
  },
  {
    label: "Owner / Admin",
    muted: true,
    items: [
      { label: "Financial dashboard", path: "/", requiresAdmin: true },
      { label: "SoftDent", path: "/softdent", requiresAdmin: true },
      { label: "QuickBooks", path: "/quickbooks", requiresAdmin: true },
      { label: "A/R details", path: "/ar", requiresAdmin: true },
      { label: "EBITDA", path: "/ebitda", requiresAdmin: true },
      { label: "Expenses", path: "/expenses", requiresAdmin: true },
      { label: "Trends", path: "/trends", requiresAdmin: true },
      { label: "Posting", path: "/posting-queue", requiresAdmin: true },
      { label: "Journal", path: "/journal-draft", requiresAdmin: true },
      { label: "Policy", path: "/accounting-policy", requiresAdmin: true },
      { label: "Settings", path: "/settings" },
      { label: "Admin", path: "/admin", requiresAdmin: true },
    ],
  },
];

function canShowItem(item: NavItem, isAuthenticated: boolean, isRoleKnown: boolean, isLoading: boolean, isAdmin: boolean) {
  if (!item.requiresAdmin) {
    return true;
  }
  if (!isAuthenticated) {
    return true;
  }
  if (!isRoleKnown || isLoading) {
    return true;
  }
  return isAdmin;
}

export default function Sidebar() {
  const { authenticatedUsername, isAuthenticated, isAdmin, isLoading, isRoleKnown, isSessionAuthenticated } = useAuthSession();
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const visibleNavGroups = useMemo(
    () =>
      navGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) => {
            if (!canShowItem(item, isAuthenticated, isRoleKnown, isLoading, isAdmin)) {
              return false;
            }

            if (!normalizedQuery) {
              return true;
            }

            return item.label.toLowerCase().includes(normalizedQuery) || group.label.toLowerCase().includes(normalizedQuery);
          }),
        }))
        .filter((group) => group.items.length > 0),
    [isAdmin, isAuthenticated, isLoading, isRoleKnown, normalizedQuery],
  );
  const sessionTitle = isSessionAuthenticated ? authenticatedUsername ?? "Connected workspace" : "Guest workspace";
  const sessionDetail = isSessionAuthenticated
    ? "Backend session is active for live dashboard, documents, and HAL data."
    : "Sign in from the banner to unlock verified accounting and HAL data.";

  return (
    <aside className="dashboard-sidebar">
      <div className="dashboard-sidebar__brand">
        <div className="dashboard-sidebar__brand-mark" aria-hidden="true">
          NR
        </div>
        <div className="dashboard-sidebar__brand-copy">
          <span className="dashboard-sidebar__brand-kicker">Financial OS</span>
          <strong>New Ridge Family Financial</strong>
        </div>
      </div>
      <label className="dashboard-sidebar__search">
        <span className="dashboard-sidebar__search-label">Quick jump</span>
        <input
          className="dashboard-sidebar__search-input"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search pages"
          aria-label="Search dashboard pages"
        />
      </label>
      <nav className="dashboard-sidebar__sections" aria-label="Primary navigation">
        {visibleNavGroups.map((group) => (
          <section
            key={group.label}
            className={group.muted ? "dashboard-sidebar__section dashboard-sidebar__section--muted" : "dashboard-sidebar__section"}
          >
            <div className="dashboard-sidebar__section-label">{group.label}</div>
            <ul className="dashboard-sidebar__nav">
              {group.items.map((item) => (
                <li key={`${group.label}-${item.label}-${item.path}`}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      isActive ? "dashboard-sidebar__link dashboard-sidebar__link--active" : "dashboard-sidebar__link"
                    }
                    end={item.path === "/"}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>
      <div className="dashboard-sidebar__footer">
        <span className="dashboard-sidebar__footer-label">Workspace</span>
        <strong>{sessionTitle}</strong>
        <span className="dashboard-sidebar__footer-copy">{sessionDetail}</span>
        <NavLink to="/settings" className="dashboard-sidebar__footer-link">
          Open settings
        </NavLink>
      </div>
    </aside>
  );
}
