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

  const body = payload as HalChatApiResponse;
  if (!body?.message) {
    throw new Error("HAL chat returned an empty response");
  }

  return body;
}
