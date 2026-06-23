import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import App from "../App";
import { clearApiBasicAuthCredentials, setApiBasicAuthCredentials } from "../api/basicAuth";
import { queryClient } from "../queryClient";

function renderAdminPage(): void {
  setApiBasicAuthCredentials("admin", "password");
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clearApiBasicAuthCredentials();
  queryClient.clear();
});

describe("accessibility", () => {
  it("has no serious axe violations on the admin dashboard", async () => {
    renderAdminPage();
    expect(await screen.findByText("SoftDent-fed financial dashboard")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: /HAL Refresh SoftDent \+ QuickBooks/i,
        }),
      ).toBeInTheDocument(),
    );

    const results = await axe.run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    expect(results.violations).toHaveLength(0);
  });
});
