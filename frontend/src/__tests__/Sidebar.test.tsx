import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useAuthSession", () => ({
  useAuthSession: vi.fn(),
}));

import Sidebar from "../layout/Sidebar";
import { useAuthSession } from "../hooks/useAuthSession";

function mockSession(overrides: Partial<ReturnType<typeof useAuthSession>> = {}) {
  vi.mocked(useAuthSession).mockReturnValue({
    authenticatedUsername: "staff",
    session: null,
    roles: [],
    isAuthenticated: true,
    isSessionAuthenticated: true,
    isSessionVerified: true,
    isLoading: false,
    isError: false,
    isRoleKnown: true,
    error: null,
    sessionStatusCode: null,
    isAdmin: false,
    retry: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useAuthSession>);
}

function renderSidebar() {
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Sidebar navigation", () => {
  it("puts staff workflows in an Office group", () => {
    mockSession();
    renderSidebar();
    expect(screen.getByText("Office")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Command Center" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Claims" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ask HAL" })).toBeInTheDocument();
  });

  it("hides source-system/financial pages from non-admin staff", () => {
    mockSession({ isAdmin: false });
    renderSidebar();
    expect(screen.queryByRole("link", { name: "SoftDent" })).toBeNull();
    expect(screen.queryByRole("link", { name: "QuickBooks" })).toBeNull();
    expect(screen.queryByRole("link", { name: "EBITDA" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Financial dashboard" })).toBeNull();
  });

  it("shows source-system/financial pages under Owner / Admin for admins", () => {
    mockSession({ isAdmin: true });
    renderSidebar();
    const ownerLabel = screen.getByText("Owner / Admin");
    const ownerSection = ownerLabel.closest("section");
    expect(ownerSection).not.toBeNull();
    const owner = within(ownerSection as HTMLElement);
    expect(owner.getByRole("link", { name: "SoftDent" })).toBeInTheDocument();
    expect(owner.getByRole("link", { name: "QuickBooks" })).toBeInTheDocument();
    expect(owner.getByRole("link", { name: "EBITDA" })).toBeInTheDocument();
    expect(owner.getByRole("link", { name: "Financial dashboard" })).toBeInTheDocument();
  });

  it("de-emphasizes the Owner / Admin section but not the Office section", () => {
    mockSession({ isAdmin: true });
    renderSidebar();
    const officeSection = screen.getByText("Office").closest("section");
    const ownerSection = screen.getByText("Owner / Admin").closest("section");
    expect(officeSection?.className).not.toContain("dashboard-sidebar__section--muted");
    expect(ownerSection?.className).toContain("dashboard-sidebar__section--muted");
  });
});
