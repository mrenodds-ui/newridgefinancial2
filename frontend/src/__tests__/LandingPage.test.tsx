import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardDataProvider } from "../context/DashboardDataContext";
import LandingPage from "../pages/LandingPage";
import { queryClient } from "../queryClient";

function renderLanding() {
  render(
    <QueryClientProvider client={queryClient}>
      <DashboardDataProvider>
        <LandingPage />
      </DashboardDataProvider>
    </QueryClientProvider>,
  );
}

describe("LandingPage", () => {
  it("renders dashboard title and dark mode toggle", () => {
    renderLanding();
    expect(screen.getByText(/Dental Practice Financial Dashboard/i)).toBeInTheDocument();
    expect(screen.getAllByTestId("dark-mode-toggle")[0]).toBeInTheDocument();
  });

  it("allows toggling dark mode", () => {
    renderLanding();
    const toggles = screen.getAllByTestId("dark-mode-toggle");
    fireEvent.click(toggles[0]);
    expect(document.querySelector(".dark")).toBeTruthy();
  });

  it("shows KPI customization checkboxes", () => {
    renderLanding();
    expect(screen.getAllByLabelText(/show date/i).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/show value/i).length).toBeGreaterThan(0);
  });

  it("filters table by search", () => {
    renderLanding();
    const search = screen.getAllByPlaceholderText(/search/i)[0];
    fireEvent.change(search, { target: { value: "2024-01" } });
    expect(search).toHaveValue("2024-01");
  });

  it("renders the interactive chart", () => {
    renderLanding();
    expect(screen.getAllByText(/Production & Collections Trend/i)[0]).toBeInTheDocument();
  });
});
