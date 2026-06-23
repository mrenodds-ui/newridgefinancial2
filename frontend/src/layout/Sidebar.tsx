import { NavLink } from "react-router-dom";

import { useAuthSession } from "../hooks/useAuthSession";

const navItems = [
  { label: "Dashboard", path: "/" },
  { label: "SoftDent", path: "/softdent" },
  { label: "QuickBooks", path: "/quickbooks" },
  { label: "EBITDA Evaluation", path: "/ebitda" },
  { label: "Expenses", path: "/expenses" },
  { label: "A/R & Collections", path: "/ar" },
  { label: "Trends", path: "/trends" },
  { label: "Claims Workbench", path: "/claims-workbench" },
  { label: "Accounting Documents", path: "/accounting-documents" },
  { label: "Document Library", path: "/document-library" },
  { label: "Accounting Policy", path: "/accounting-policy" },
  { label: "Journal Draft", path: "/journal-draft" },
  { label: "Posting Queue", path: "/posting-queue" },
  { label: "Admin", path: "/admin", requiresAdmin: true },
  { label: "Ask Hal 9000", path: "/hal" },
  { label: "Hal 9000 Landing", path: "/hal-landing" },
  { label: "Settings", path: "/settings" },
];

export default function Sidebar() {
  const { isAuthenticated, isAdmin, isLoading, isRoleKnown } = useAuthSession();
  const visibleNavItems = navItems.filter((item) => {
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
  });

  return (
    <aside className="dashboard-sidebar">
      <div className="dashboard-sidebar__brand">New Ridge Family Financial</div>
      <ul className="dashboard-sidebar__nav">
        {visibleNavItems.map((item) => (
          <li key={item.path}>
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
    </aside>
  );
}
