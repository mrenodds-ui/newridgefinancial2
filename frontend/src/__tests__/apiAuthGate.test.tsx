import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import App from "../App";
import { clearApiBasicAuthCredentials, setApiAuthenticatedUsername } from "../api/basicAuth";
import { DashboardDataProvider } from "../context/DashboardDataContext";
import { server } from "../mocks/server";
import { queryClient } from "../queryClient";

type MockAuthUsername = "admin" | "viewer" | "operator";

function buildAuthSession(username: MockAuthUsername) {
  if (username === "operator") {
    return {
      username: "operator",
      display_name: "Operator",
      roles: ["hal:operator"],
    };
  }

  if (username === "viewer") {
    return {
      username: "viewer",
      display_name: "Viewer",
      roles: ["dashboard:read"],
    };
  }

  return {
    username: "admin",
    display_name: "Administrator",
    roles: ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
  };
}

function buildDashboardFinancialSummary() {
  return {
    generatedAt: "2026-06-22T10:00:00Z",
    latestSoftDentRefreshAt: "2026-06-22T09:30:00Z",
    dataFreshnessStatus: "fresh",
    latestAr: {
      as_of_date: "2026-06-22",
      total_ar: 12000,
      insurance_ar: 5000,
      patient_ar: 7000,
      current_balance: 6000,
      balance_30: 3000,
      balance_60: 2000,
      balance_90: 1000,
      credit_balance: 0,
    },
    monthlyKpis: [{ year_month: "2026-06", gross_production: 2500, collections: 2100, collection_rate: 84 }],
    trailing12Months: [],
    calendarYearKpis: [],
    fourYearMonthlyKpis: [],
    providerProduction: [],
    topAdaCodes: [],
    quickBooksExpenseCategories: [{ expense_category: "Payroll", total_amount: 1800 }],
    quickBooksProfitLossSummary: [{ year_month: "2026-06", income_total: 5100, expense_total: 3200, net_income: 1900 }],
    quickBooksMonthlyExpenses: [],
    quickBooksEbitdaCandidates: [],
  };
}

function renderApp(pathname: string): void {
  cleanup();
  queryClient.clear();
  render(
    <QueryClientProvider client={queryClient}>
      <DashboardDataProvider>
        <MemoryRouter basename="/app" initialEntries={[pathname]}>
          <App />
        </MemoryRouter>
      </DashboardDataProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clearApiBasicAuthCredentials();
  queryClient.clear();
  cleanup();
});

describe("API auth gate", () => {
  it("keeps the dashboard summary quiet until sign-in and then reloads it", async () => {
    let activeUsername: MockAuthUsername | null = null;
    let financialSummaryRequestCount = 0;

    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        const payload = (await request.json()) as { username?: string; password?: string };
        if (payload.username === "admin" && payload.password === "password") {
          activeUsername = "admin";
          return HttpResponse.json(buildAuthSession("admin"));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/auth/session", () => {
        if (activeUsername) {
          return HttpResponse.json(buildAuthSession(activeUsername));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/hal9000/page-summary", () => {
        financialSummaryRequestCount += 1;
        if (activeUsername === "admin") {
          return HttpResponse.json(buildDashboardFinancialSummary());
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
    );

    renderApp("/app/");

    expect(
      await screen.findByText(
        "Sign in from the dashboard banner to load the verified financial summary. Import-preview charts and CSV inspection remain available below.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument();
    expect(financialSummaryRequestCount).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to New Ridge Dashboard" });

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument());

    expect(await screen.findByText("Connected as admin")).toBeInTheDocument();
    expect(await screen.findByText("$2,500")).toBeInTheDocument();
    expect(await screen.findByText("$1,900")).toBeInTheDocument();
    expect(financialSummaryRequestCount).toBeGreaterThan(0);
  });

  it("keeps dashboard summary data hidden while a cached username waits on session verification", async () => {
    let financialSummaryRequestCount = 0;
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => new Promise(() => {})),
      http.get("/api/hal9000/page-summary", () => {
        financialSummaryRequestCount += 1;
        return HttpResponse.json(buildDashboardFinancialSummary());
      }),
    );

    renderApp("/app/");

    expect(await screen.findByText("Verifying session...")).toBeInTheDocument();
    expect(screen.queryByText("Connected as admin")).not.toBeInTheDocument();
    expect(await screen.findByText("Loading verified financial summary...")).toBeInTheDocument();
    expect(screen.queryByText("$2,500")).not.toBeInTheDocument();
    expect(screen.queryByText("$1,900")).not.toBeInTheDocument();
    expect(financialSummaryRequestCount).toBe(0);
  });

  it("does not render dashboard summary data when cached username fails session verification", async () => {
    let financialSummaryRequestCount = 0;
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json({ detail: "session backend unavailable" }, { status: 500 })),
      http.get("/api/hal9000/page-summary", () => {
        financialSummaryRequestCount += 1;
        return HttpResponse.json(buildDashboardFinancialSummary());
      }),
    );

    renderApp("/app/");

    expect(await screen.findByText("Session verification unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Connected as admin")).not.toBeInTheDocument();
    expect(
      await screen.findByText(
        "Sign in from the dashboard banner to load the verified financial summary. Import-preview charts and CSV inspection remain available below.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("$2,500")).not.toBeInTheDocument();
    expect(screen.queryByText("$1,900")).not.toBeInTheDocument();
    expect(financialSummaryRequestCount).toBe(0);
  });

  it("renders dashboard summary data after a cached username is re-verified by the backend session", async () => {
    let financialSummaryRequestCount = 0;
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json(buildAuthSession("admin"))),
      http.get("/api/hal9000/page-summary", () => {
        financialSummaryRequestCount += 1;
        return HttpResponse.json(buildDashboardFinancialSummary());
      }),
    );

    renderApp("/app/");

    expect(await screen.findByText("$2,500")).toBeInTheDocument();
    expect(await screen.findByText("$1,900")).toBeInTheDocument();
    expect(financialSummaryRequestCount).toBeGreaterThan(0);
  });

  it("keeps the document library quiet until sign-in and then reloads it", async () => {
    let activeUsername: MockAuthUsername | null = null;
    let documentLibraryRequestCount = 0;

    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        const payload = (await request.json()) as { username?: string; password?: string };
        if (payload.username === "admin" && payload.password === "password") {
          activeUsername = "admin";
          return HttpResponse.json(buildAuthSession("admin"));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/auth/session", () => {
        if (activeUsername) {
          return HttpResponse.json(buildAuthSession(activeUsername));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/hal9000/document-rag/documents", () => {
        documentLibraryRequestCount += 1;
        if (activeUsername === "admin") {
          return HttpResponse.json({
            count: 1,
            limit: 25,
            search: null,
            items: [
              {
                document_id: "doc-mock-001",
                source_name: "q2-earnings-notes.md",
                stored_path: "document_rag/uploads/doc-mock-001-q2-earnings-notes.md",
                mime_type: "text/markdown",
                sha256: "mock-doc-sha-1",
                uploaded_at_utc: "2026-06-21T14:10:00Z",
                uploaded_by: "admin",
                page_count: 1,
                chunk_count: 2,
                content_char_count: 284,
              },
            ],
          });
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
    );

    renderApp("/app/document-library");

    expect(await screen.findByText("Sign in from the dashboard banner to load the document library.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument();
    expect(documentLibraryRequestCount).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to New Ridge Dashboard" });

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument());
    expect(await screen.findByText("Connected as admin")).toBeInTheDocument();
    expect(await screen.findByText("q2-earnings-notes.md")).toBeInTheDocument();
    expect(documentLibraryRequestCount).toBeGreaterThan(0);
  });

  it("keeps the A/R summary quiet until sign-in and then reloads it", async () => {
    let activeUsername: MockAuthUsername | null = null;
    let financialSummaryRequestCount = 0;

    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        const payload = (await request.json()) as { username?: string; password?: string };
        if (payload.username === "admin" && payload.password === "password") {
          activeUsername = "admin";
          return HttpResponse.json(buildAuthSession("admin"));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/auth/session", () => {
        if (activeUsername) {
          return HttpResponse.json(buildAuthSession(activeUsername));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/hal9000/page-summary", () => {
        financialSummaryRequestCount += 1;
        if (activeUsername === "admin") {
          return HttpResponse.json({
            latestAr: {
              as_of_date: "2026-06",
              total_ar: 9765,
              insurance_ar: 0,
              patient_ar: 0,
              current_balance: 9765,
              balance_30: 0,
              balance_60: 0,
              balance_90: 0,
              credit_balance: 0,
            },
            monthlyKpis: [
              {
                year_month: "2026-06",
                collections: 107015,
                collection_rate: 91.64,
              },
            ],
            trailing12Months: [
              { year_month: "2026-05", collections: 103250 },
              { year_month: "2026-06", collections: 107015 },
            ],
            sourceReview: {
              softDent: {
                sourceSystem: "SoftDent",
                status: "ready",
                summary: "SoftDent live snapshot for 2026-06.",
                confidenceLabel: "high confidence",
                reviewRequired: false,
                reviewFlags: [],
                lastVerifiedAt: "2026-06-21T21:38:09.549167+00:00",
                metrics: {
                  period: "2026-06",
                  provider_count: 3,
                },
              },
            },
            healthFlags: [],
          });
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
    );

    renderApp("/app/ar");

    expect(await screen.findByText("Sign in from the dashboard banner to load the A/R and collections page.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument();
    expect(financialSummaryRequestCount).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to New Ridge Dashboard" });

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Loading A/R and collections...")).not.toBeInTheDocument());

    expect(await screen.findByText("Connected as admin")).toBeInTheDocument();
    expect(await screen.findByText("$9,765")).toBeInTheDocument();
    expect(await screen.findByText("SoftDent live snapshot for 2026-06.")).toBeInTheDocument();
    expect(financialSummaryRequestCount).toBeGreaterThan(0);
  });

  it("blocks the admin console for authenticated viewers without firing admin-only queries", async () => {
    let activeUsername: MockAuthUsername | null = null;
    let adminSummaryRequestCount = 0;

    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        const payload = (await request.json()) as { username?: string; password?: string };
        if (payload.username === "viewer" && payload.password === "viewer-password") {
          activeUsername = "viewer";
          return HttpResponse.json(buildAuthSession("viewer"));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/auth/session", () => {
        if (activeUsername) {
          return HttpResponse.json(buildAuthSession(activeUsername));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/hal9000/admin-summary", () => {
        adminSummaryRequestCount += 1;
        return HttpResponse.json({ detail: "forbidden" }, { status: 403 });
      }),
    );

    renderApp("/app/admin");

    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to New Ridge Dashboard" });

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "viewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "viewer-password" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument());

    expect(await screen.findByText("Admin Access Required")).toBeInTheDocument();
    expect(screen.getByText(/Signed-in viewer accounts can continue using the reporting pages/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
    expect(adminSummaryRequestCount).toBe(0);
  });

  it("shows an admin-session error state instead of downgrading a signed-in admin to viewer", async () => {
    let activeUsername: MockAuthUsername | null = null;
    let adminSummaryRequestCount = 0;

    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        const payload = (await request.json()) as { username?: string; password?: string };
        if (payload.username === "admin" && payload.password === "password") {
          activeUsername = "admin";
          return HttpResponse.json(buildAuthSession("admin"));
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/auth/session", () => {
        if (activeUsername === "admin") {
          return HttpResponse.json({ detail: "session backend unavailable" }, { status: 500 });
        }
        return HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 });
      }),
      http.get("/api/hal9000/admin-summary", () => {
        adminSummaryRequestCount += 1;
        return HttpResponse.json({ detail: "forbidden" }, { status: 403 });
      }),
    );

    renderApp("/app/admin");

    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to New Ridge Dashboard" });

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "admin" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Sign in to New Ridge Dashboard" })).not.toBeInTheDocument());

    expect(await screen.findByText("Admin Session Check Failed")).toBeInTheDocument();
    expect(screen.getByText(/session backend unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("Admin Access Required")).not.toBeInTheDocument();
    expect(adminSummaryRequestCount).toBe(0);
  });

  it("renders the journal draft page only after cached username passes session verification", async () => {
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json(buildAuthSession("admin"))),
    );

    renderApp("/app/journal-draft");

    expect(await screen.findByText("Journal Draft Review")).toBeInTheDocument();
    expect(screen.getByLabelText("Raw Source Text")).toBeInTheDocument();
  });

  it("does not render the journal draft page when cached username fails with 401", async () => {
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json({ detail: "Incorrect username or password" }, { status: 401 })),
    );

    renderApp("/app/journal-draft");

    expect(await screen.findByText("Sign in from the dashboard banner to load the journal draft review page.")).toBeInTheDocument();
    expect(screen.queryByText("Journal Draft Review")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Raw Source Text")).not.toBeInTheDocument();
  });

  it("does not render the journal draft page when cached username fails session verification", async () => {
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json({ detail: "session backend unavailable" }, { status: 500 })),
    );

    renderApp("/app/journal-draft");

    expect(await screen.findByText(/The dashboard session could not be verified right now/i)).toBeInTheDocument();
    expect(screen.queryByText("Journal Draft Review")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Raw Source Text")).not.toBeInTheDocument();
  });

  it("does not render the posting queue route for authenticated users without the operator role", async () => {
    setApiAuthenticatedUsername("viewer");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json(buildAuthSession("viewer"))),
    );

    renderApp("/app/posting-queue");

    expect(await screen.findByText(/not authorized to load the posting queue review page/i)).toBeInTheDocument();
    expect(screen.queryByText("Posting Queue Review")).not.toBeInTheDocument();
  });

  it("does not render the claims workbench for operators missing dashboard read access", async () => {
    setApiAuthenticatedUsername("operator");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json(buildAuthSession("operator"))),
    );

    renderApp("/app/claims-workbench");

    expect(await screen.findByText(/not authorized to load the claims workbench/i)).toBeInTheDocument();
    expect(screen.queryByText("Patient Claims Workbench")).not.toBeInTheDocument();
  });

  it("renders the accounting policy page for authenticated users with the operator role", async () => {
    setApiAuthenticatedUsername("admin");

    server.use(
      http.get("/api/auth/session", () => HttpResponse.json(buildAuthSession("admin"))),
    );

    renderApp("/app/accounting-policy");

    expect(await screen.findByText("Accounting Policy Guidance")).toBeInTheDocument();
    expect(screen.getByLabelText("Policy Question")).toBeInTheDocument();
  });
});
