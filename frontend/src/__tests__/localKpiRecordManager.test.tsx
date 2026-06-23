import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { LocalKpiRecordManager } from "../components/LocalKpiRecordManager";
import { db } from "../db";
import { clearKpiRecords } from "../kpiRecords";

function renderManager(): void {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <LocalKpiRecordManager />
    </QueryClientProvider>,
  );
}

describe("LocalKpiRecordManager", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(async () => {
    db.close();
    await db.delete();
    await db.open();
    await clearKpiRecords();
  });

  it("renders the form and empty state", async () => {
    renderManager();

    expect(await screen.findByRole("heading", { name: "Local KPI Records" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save record" })).toBeInTheDocument();
    expect(await screen.findByText("No saved KPI records")).toBeInTheDocument();
  });

  it("shows a validation error for invalid input", async () => {
    renderManager();

    fireEvent.change(screen.getByLabelText("Period"), {
      target: { value: "bad" },
    });
    fireEvent.change(screen.getByLabelText("Production"), {
      target: { value: "-1" },
    });
    fireEvent.change(screen.getByLabelText("Collections"), {
      target: { value: "100" },
    });
    fireEvent.change(screen.getByLabelText("Overhead %"), {
      target: { value: "120" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save record" }));

    expect(await screen.findByText("Use YYYY-MM format.")).toBeInTheDocument();
    expect(screen.getByText("Production must be 0 or more.")).toBeInTheDocument();
    expect(screen.getByText("Overhead must be 100 or less.")).toBeInTheDocument();
  });

  it("creates, edits, and deletes a record", async () => {
    renderManager();

    fireEvent.change(screen.getByLabelText("Period"), {
      target: { value: "2026-05" },
    });
    fireEvent.change(screen.getByLabelText("Production"), {
      target: { value: "135000" },
    });
    fireEvent.change(screen.getByLabelText("Collections"), {
      target: { value: "126500" },
    });
    fireEvent.change(screen.getByLabelText("Overhead %"), {
      target: { value: "26" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save record" }));

    expect(await screen.findByText("2026-05")).toBeInTheDocument();
    expect(screen.getByText("Production: 135,000")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Update record" })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Period"), {
      target: { value: "2026-06" },
    });
    fireEvent.change(screen.getByLabelText("Production"), {
      target: { value: "140000" },
    });
    fireEvent.change(screen.getByLabelText("Collections"), {
      target: { value: "130000" },
    });
    fireEvent.change(screen.getByLabelText("Overhead %"), {
      target: { value: "24" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update record" }));

    expect(await screen.findByText("2026-06")).toBeInTheDocument();
    expect(screen.queryByText("2026-05")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("No saved KPI records")).toBeInTheDocument();
  });
});
