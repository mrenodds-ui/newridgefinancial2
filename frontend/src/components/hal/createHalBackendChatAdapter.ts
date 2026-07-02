import type { ChatModelAdapter, ThreadMessage } from "@assistant-ui/react";

import { type HalChatApiMessage, postHalChat } from "./halChatApi";
import type { HalPageContext } from "./useHalPageContext";

function threadMessageText(message: ThreadMessage): string {
  return message.content
    .flatMap((part) => (part.type === "text" ? [part.text] : []))
    .join("\n")
    .trim();
}

function toApiHistory(messages: readonly ThreadMessage[]): HalChatApiMessage[] {
  return messages
    .map((message) => {
      const content = threadMessageText(message);
      if (!content) {
        return null;
      }
      if (message.role !== "user" && message.role !== "assistant") {
        return null;
      }
      return { role: message.role, content };
    })
    .filter((item): item is HalChatApiMessage => item !== null)
    .slice(-8);
}

export function createHalBackendChatAdapter(getPageContext: () => HalPageContext): ChatModelAdapter {
  return {
    async run({ messages, abortSignal }) {
      const latestUser = [...messages].reverse().find((message) => message.role === "user");
      const message = latestUser ? threadMessageText(latestUser) : "";
      if (!message) {
        return {
          content: [{ type: "text", text: "Please enter a message for HAL." }],
        };
      }

      const history = toApiHistory(messages.slice(0, -1));
      const pageContext = getPageContext();
      const response = await postHalChat(
        {
          message,
          pageContext: {
            route: pageContext.route,
            pageTitle: pageContext.pageTitle,
            capturedAt: pageContext.capturedAt,
          },
          history,
        },
        abortSignal,
      );

      return {
        content: [{ type: "text", text: response.message }],
      };
    },
  };
}
