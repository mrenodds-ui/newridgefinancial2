export type BrowserSyncTopic =
  | "kpis-updated"
  | "preferences-updated"
  | "import-jobs-updated"
  | "admin-refreshed"
  | "backup-restored"
  | "cache-invalidated"
  | "session-cleared";

export interface BrowserSyncMessage {
  topic: BrowserSyncTopic;
  timestamp: string;
}

export interface BrowserSyncChannel {
  supported: boolean;
  post: (message: BrowserSyncMessage) => boolean;
  close: () => void;
}

export function createBrowserSyncMessage(topic: BrowserSyncTopic): BrowserSyncMessage {
  return {
    topic,
    timestamp: new Date().toISOString(),
  };
}

export function createCacheInvalidatedMessage(): BrowserSyncMessage {
  return createBrowserSyncMessage("cache-invalidated");
}

export function createSessionClearedMessage(): BrowserSyncMessage {
  return createBrowserSyncMessage("session-cleared");
}

export function createBrowserSyncSubscriber(
  onMessage: (message: BrowserSyncMessage) => void,
  channelName = "newridge-financial-sync",
  globalScope: typeof globalThis = globalThis,
): BrowserSyncChannel {
  const BroadcastChannelImpl = globalScope.BroadcastChannel;
  if (!BroadcastChannelImpl) {
    return {
      supported: false,
      post: () => false,
      close: () => undefined,
    };
  }

  const channel = new BroadcastChannelImpl(channelName);
  channel.onmessage = (event: MessageEvent<BrowserSyncMessage>) => {
    const message = event.data;
    if (!message?.topic) return;
    onMessage(message);
  };

  return {
    supported: true,
    post: (message: BrowserSyncMessage) => {
      channel.postMessage(message);
      return true;
    },
    close: () => channel.close(),
  };
}

export function broadcastBrowserSyncMessage(
  message: BrowserSyncMessage,
  channelName = "newridge-financial-sync",
  globalScope: typeof globalThis = globalThis,
): boolean {
  const BroadcastChannelImpl = globalScope.BroadcastChannel;
  if (!BroadcastChannelImpl) return false;
  const channel = new BroadcastChannelImpl(channelName);
  channel.postMessage(message);
  channel.close();
  return true;
}
