export type HalServerStatus = "online" | "offline" | "degraded" | "unknown";
export type HalModelStatus = "ready" | "not_configured" | "blocked" | "unknown";
export type HalSourceAccessMode = "read_only" | "write_enabled" | "blocked" | "unknown";

export type HalSourceIntakeStatus = "ingested" | "pending" | "blocked" | "error" | "unknown";
export type HalWorkSurfaceStatus = "active" | "inactive" | "blocked" | "unknown";
export type HalActivityStatus = "success" | "blocked" | "error" | "info";
export type HalInsightConfidence = "low" | "medium" | "high" | "unknown";

export type HalCommandCenterState = {
  currentMode: string;
  serverStatus: HalServerStatus;
  modelStatus: HalModelStatus;
  sourceAccessMode: HalSourceAccessMode;
  sourceIntake: Array<{
    source: string;
    type: string;
    lastIngested: string | null;
    status: HalSourceIntakeStatus;
  }>;
  workSurfaces: Array<{
    id: string;
    title: string;
    status: HalWorkSurfaceStatus;
    updatedAt: string | null;
    itemCount: number | null;
  }>;
  recentActivity: Array<{
    id: string;
    label: string;
    createdAt: string;
    status: HalActivityStatus;
  }>;
  insights: Array<{
    id: string;
    label: string;
    confidence: HalInsightConfidence;
    createdAt: string | null;
  }>;
  permissions: {
    canAskHal: boolean;
    canReadSources: boolean;
    canWriteSources: boolean;
    requiresApproval: boolean;
  };
  verificationReceipt: {
    generatedAt: string;
    source: string;
    mockDataUsed: boolean;
    permissionsApplied: boolean;
  };
  suggestions?: string[];
  firewallBlockedActions?: string[];
};

export type HalAskResponse = {
  status: "ok" | "blocked" | "unavailable" | "error";
  text: string;
  lane: string;
  intent: string;
  receipt: {
    generatedAt: string;
    mockDataUsed: boolean;
    blocked?: boolean;
    error?: string;
  };
};
