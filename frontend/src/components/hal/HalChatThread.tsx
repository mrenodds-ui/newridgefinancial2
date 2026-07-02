import { ComposerPrimitive, MessagePartPrimitive, MessagePrimitive, ThreadPrimitive, useAui } from "@assistant-ui/react";

import { HAL_GREETING_SUBTITLE, HAL_GREETING_TITLE, HAL_SAFETY_BOUNDARIES, halRuntimeNote } from "./halChatConstants";

function HalChatEmptyState() {
  return (
    <div className="hal-chat-empty">
      <div className="hal-chat-empty__badge" aria-hidden="true">
        HAL
      </div>
      <h3 className="hal-chat-empty__title">{HAL_GREETING_TITLE}</h3>
      <p className="hal-chat-empty__subtitle">{HAL_GREETING_SUBTITLE}</p>
      <p className="hal-chat-empty__safety-lead">HAL is limited to safe internal assistance. Current boundaries:</p>
      <ul className="hal-chat-empty__boundaries">
        {HAL_SAFETY_BOUNDARIES.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="hal-chat-empty__note">{halRuntimeNote()}</p>
    </div>
  );
}

function HalChatClearButton() {
  const aui = useAui();

  return (
    <button
      type="button"
      className="hal-chat-header__action"
      onClick={() => {
        aui.thread().reset();
      }}
    >
      Clear
    </button>
  );
}

function HalChatRunningIndicator() {
  return (
    <div className="hal-chat-running" aria-live="polite" aria-label="HAL is thinking">
      <span className="hal-chat-running__dot" />
      <span className="hal-chat-running__dot" />
      <span className="hal-chat-running__dot" />
      <span className="hal-chat-running__label">HAL is thinking…</span>
    </div>
  );
}

function HalChatMessage() {
  return (
    <MessagePrimitive.Root className="hal-chat-message">
      <MessagePrimitive.If user>
        <div className="hal-chat-message__row hal-chat-message__row--user">
          <div className="hal-chat-message__bubble hal-chat-message__bubble--user">
            <MessagePrimitive.Parts
              components={{
                Text: () => <MessagePartPrimitive.Text className="hal-chat-message__text" />,
              }}
            />
          </div>
        </div>
      </MessagePrimitive.If>
      <MessagePrimitive.If assistant>
        <div className="hal-chat-message__row hal-chat-message__row--assistant">
          <div className="hal-chat-message__avatar" aria-hidden="true">
            HAL
          </div>
          <div className="hal-chat-message__bubble hal-chat-message__bubble--assistant">
            <MessagePrimitive.Parts
              components={{
                Text: () => <MessagePartPrimitive.Text className="hal-chat-message__text" />,
              }}
            />
          </div>
        </div>
      </MessagePrimitive.If>
    </MessagePrimitive.Root>
  );
}

export function HalChatThread() {
  return (
    <ThreadPrimitive.Root className="hal-chat-thread">
      <ThreadPrimitive.Viewport className="hal-chat-thread__viewport">
        <ThreadPrimitive.If empty>
          <HalChatEmptyState />
        </ThreadPrimitive.If>

        <ThreadPrimitive.Messages
          components={{
            Message: HalChatMessage,
          }}
        />

        <ThreadPrimitive.If running>
          <HalChatRunningIndicator />
        </ThreadPrimitive.If>
      </ThreadPrimitive.Viewport>

      <div className="hal-chat-composer">
        <ComposerPrimitive.Root className="hal-chat-composer__root">
          <ComposerPrimitive.Input
            className="hal-chat-composer__input"
            placeholder="Ask HAL about dashboards, reports, or office workflows…"
            rows={1}
            aria-label="Message HAL"
          />
          <ComposerPrimitive.Send className="hal-chat-composer__send" aria-label="Send message">
            Send
          </ComposerPrimitive.Send>
        </ComposerPrimitive.Root>
      </div>
    </ThreadPrimitive.Root>
  );
}

export function HalChatPanelHeader({ onMinimize }: { onMinimize: () => void }) {
  return (
    <header className="hal-chat-header">
      <div className="hal-chat-header__brand">
        <span className="hal-chat-header__mark" aria-hidden="true">
          HAL
        </span>
        <div>
          <p className="hal-chat-header__title">HAL Assistant</p>
          <p className="hal-chat-header__subtitle">Safe internal assistance</p>
        </div>
      </div>
      <div className="hal-chat-header__actions">
        <HalChatClearButton />
        <button
          type="button"
          className="hal-chat-header__action hal-chat-header__action--icon"
          aria-label="Minimize HAL chat"
          onClick={onMinimize}
        >
          —
        </button>
      </div>
    </header>
  );
}
