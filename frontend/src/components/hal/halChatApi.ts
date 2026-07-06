import { config } from "../../config";

export type HalChatApiMessage = {
  role: "user" | "assistant";
  content: string;
};

export type HalChatApiPageContext = {
  route: string;
  pageTitle: string;
  capturedAt: string;
};

export type HalChatApiRequest = {
  message: string;
  pageContext?: HalChatApiPageContext;
  history?: HalChatApiMessage[];
};

export type HalChatApiResponse = {
  message: string;
  mode: string;
  localAiUnavailable?: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseHalChatApiResponse(payload: unknown): HalChatApiResponse {
  if (!isRecord(payload)) {
    throw new Error("HAL chat returned an invalid response payload");
  }

  const { message, mode, localAiUnavailable } = payload;
  if (typeof message !== "string" || !message.trim()) {
    throw new Error("HAL chat returned an empty response");
  }
  if (typeof mode !== "string" || !mode.trim()) {
    throw new Error("HAL chat returned an invalid mode");
  }
  if (localAiUnavailable !== undefined && localAiUnavailable !== null && typeof localAiUnavailable !== "string") {
    throw new Error("HAL chat returned an invalid availability flag");
  }

  return {
    message,
    mode,
    localAiUnavailable: localAiUnavailable ?? null,
  };
}

export async function postHalChat(request: HalChatApiRequest, signal?: AbortSignal): Promise<HalChatApiResponse> {
  const response = await fetch(`${config.apiBaseUrl}/hal/chat`, {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: request.message,
      pageContext: request.pageContext,
      history: request.history,
    }),
    signal,
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `HAL chat request failed (${response.status})`;
    throw new Error(detail);
  }

  return parseHalChatApiResponse(payload);
}
