import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HAL_MOCK_ASSISTANT_RESPONSE, HAL_SAFETY_BOUNDARIES } from "../components/hal/halChatConstants";
import AppShell from "../layout/AppShell";

const fetchAuthSessionMock = vi.fn();
const postHalChatMock = vi.fn();

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    fetchAuthSession: (...args: Parameters<typeof actual.fetchAuthSession>) => fetchAuthSessionMock(...args),
  };
});

vi.mock("../components/hal/halChatApi", () => ({
  postHalChat: (...args: unknown[]) => postHalChatMock(...args),
}));

function renderProtectedAppShell() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <AppShell>
          <div>Dashboard content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchAuthSessionMock.mockResolvedValue({
    username: "office.manager",
    display_name: "Office Manager",
    roles: ["dashboard:read"],
  });
  postHalChatMock.mockResolvedValue({
    message: "Backend HAL reply for tests.",
    mode: "local-ollama",
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("HalChatWidget", () => {
  it("renders the HAL chat button in the protected app shell", async () => {
    renderProtectedAppShell();

    expect(await screen.findByTestId("hal-chat-trigger")).toBeInTheDocument();
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });

  it("opens the panel and shows greeting and safety boundaries", async () => {
    renderProtectedAppShell();

    fireEvent.click(await screen.findByTestId("hal-chat-trigger"));

    expect(screen.getByTestId("hal-chat-panel")).toBeInTheDocument();
    expect(screen.getByText("Hi, I'm HAL")).toBeInTheDocument();
    expect(screen.getByText(/limited to safe internal assistance/i)).toBeInTheDocument();

    for (const boundary of HAL_SAFETY_BOUNDARIES) {
      expect(screen.getByText(boundary)).toBeInTheDocument();
    }
  });

  it("adds the user message and backend assistant response", async () => {
    renderProtectedAppShell();
    fireEvent.click(await screen.findByTestId("hal-chat-trigger"));

    const panel = screen.getByTestId("hal-chat-panel");
    const input = within(panel).getByRole("textbox", { name: "Message HAL" });

    fireEvent.change(input, { target: { value: "What can HAL do right now?" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Send message" }));

    expect(within(panel).getByText("What can HAL do right now?")).toBeInTheDocument();

    await waitFor(
      () => {
        expect(within(panel).getByText("Backend HAL reply for tests.")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    expect(postHalChatMock).toHaveBeenCalledTimes(1);
    expect(postHalChatMock.mock.calls[0]?.[0]).toMatchObject({
      message: "What can HAL do right now?",
    });
  });

  it("clears the conversation", async () => {
    renderProtectedAppShell();
    fireEvent.click(await screen.findByTestId("hal-chat-trigger"));

    const panel = screen.getByTestId("hal-chat-panel");
    const input = within(panel).getByRole("textbox", { name: "Message HAL" });

    fireEvent.change(input, { target: { value: "Temporary message" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Send message" }));

    await waitFor(
      () => {
        expect(within(panel).getByText("Temporary message")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    await waitFor(
      () => {
        expect(within(panel).getByText("Backend HAL reply for tests.")).toBeInTheDocument();
      },
      { timeout: 3000 },
    );

    fireEvent.click(within(panel).getByRole("button", { name: "Clear" }));

    await waitFor(() => {
      expect(within(panel).queryByText("Temporary message")).not.toBeInTheDocument();
    });
    expect(within(panel).getByText("Hi, I'm HAL")).toBeInTheDocument();
  });

  it("hides the widget when the session is unauthenticated", async () => {
    fetchAuthSessionMock.mockRejectedValue(Object.assign(new Error("Unauthorized"), { status: 401 }));

    renderProtectedAppShell();

    await waitFor(() => {
      expect(screen.queryByTestId("hal-chat-trigger")).not.toBeInTheDocument();
    });
  });

  it("hides the widget when the user lacks HAL chat roles", async () => {
    fetchAuthSessionMock.mockResolvedValue({
      username: "guest",
      display_name: "Guest",
      roles: ["reports:read"],
    });

    renderProtectedAppShell();

    await waitFor(() => {
      expect(screen.queryByTestId("hal-chat-trigger")).not.toBeInTheDocument();
    });
  });

  it("shows the widget for hal:operator role", async () => {
    fetchAuthSessionMock.mockResolvedValue({
      username: "hal.ops",
      display_name: "HAL Operator",
      roles: ["hal:operator"],
    });

    renderProtectedAppShell();

    expect(await screen.findByTestId("hal-chat-trigger")).toBeInTheDocument();
  });
});

describe("HalChatWidget mock mode", () => {
  it("uses the local mock adapter when VITE_HAL_CHAT_MODE=mock", async () => {
    vi.stubEnv("VITE_HAL_CHAT_MODE", "mock");
    renderProtectedAppShell();
    fireEvent.click(await screen.findByTestId("hal-chat-trigger"));

    const panel = screen.getByTestId("hal-chat-panel");
    const input = within(panel).getByRole("textbox", { name: "Message HAL" });
    fireEvent.change(input, { target: { value: "Mock mode check" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Send message" }));

    await waitFor(
      () => {
        expect(within(panel).getByText(HAL_MOCK_ASSISTANT_RESPONSE)).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
    expect(postHalChatMock).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });
});
