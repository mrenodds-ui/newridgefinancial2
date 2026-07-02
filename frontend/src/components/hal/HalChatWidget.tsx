import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { useMemo, useRef, useState } from "react";

import { HalChatPanelHeader, HalChatThread } from "./HalChatThread";
import { createHalBackendChatAdapter } from "./createHalBackendChatAdapter";
import { createHalMockChatAdapter } from "./createHalMockChatAdapter";
import { isHalMockChatMode } from "./halChatConstants";
import { useHalChatAccess } from "./useHalChatAccess";
import { useHalPageContext } from "./useHalPageContext";
import "./HalChatWidget.css";

function HalChatWidgetPanel() {
  const pageContext = useHalPageContext();
  const pageContextRef = useRef(pageContext);
  pageContextRef.current = pageContext;
  const useMockChat = isHalMockChatMode();

  const adapter = useMemo(
    () =>
      useMockChat ? createHalMockChatAdapter(() => pageContextRef.current) : createHalBackendChatAdapter(() => pageContextRef.current),
    [useMockChat],
  );
  const runtime = useLocalRuntime(adapter);
  const [open, setOpen] = useState(false);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="hal-chat-widget" data-testid="hal-chat-widget">
        {open ? (
          <section className="hal-chat-panel" aria-label="HAL assistant chat" data-testid="hal-chat-panel">
            <HalChatPanelHeader onMinimize={() => setOpen(false)} />
            <HalChatThread />
          </section>
        ) : null}

        <button
          type="button"
          className="hal-chat-trigger"
          aria-expanded={open}
          aria-controls="hal-chat-panel-region"
          data-testid="hal-chat-trigger"
          onClick={() => setOpen((value) => !value)}
        >
          <span className="hal-chat-trigger__icon" aria-hidden="true">
            HAL
          </span>
          <span>{open ? "Hide HAL" : "Ask HAL"}</span>
        </button>
      </div>
    </AssistantRuntimeProvider>
  );
}

export function HalChatWidget() {
  const canShowHalChat = useHalChatAccess();

  if (!canShowHalChat) {
    return null;
  }

  return <HalChatWidgetPanel />;
}
