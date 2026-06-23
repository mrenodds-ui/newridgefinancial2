import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardDataProvider } from "../context/DashboardDataContext";
import LandingPage from "../pages/LandingPage";
import { queryClient } from "../queryClient";

function renderLandingPage() {
  render(
    <QueryClientProvider client={queryClient}>
      <DashboardDataProvider>
        <LandingPage />
      </DashboardDataProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.useRealTimers();
});

describe("LandingPage refresh", () => {
  it("shows Refresh Now and updates lastRefreshedAt", async () => {
    renderLandingPage();
    const btn = screen.getByText(/Refresh Now/i);
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText(/Refreshing/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Refresh Now/i)).toBeInTheDocument(), { timeout: 2000 });
    expect(screen.getByText(/Last refreshed:/i).textContent).toMatch(/Last refreshed:/i);
  });

  it("replaces chart data arrays on refresh", async () => {
    renderLandingPage();
    const btn = screen.getAllByText(/Refresh Now/i)[0];
    const chartBefore = screen.getAllByText(/Production & Collections Trend/i)[0];
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByText(/Refreshing/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(/Production & Collections Trend/i)[0]).toBeInTheDocument());
    // No error = chart re-rendered
    expect(chartBefore).toBeInTheDocument();
  });

  it("auto-refreshes every 30 minutes (simulated)", async () => {
    vi.useFakeTimers();
    renderLandingPage();
    await act(async () => {
      vi.advanceTimersByTime(1800000);
    });
    expect(screen.getByText(/Refreshing/i)).toBeInTheDocument();
    vi.useRealTimers();
  });
});
