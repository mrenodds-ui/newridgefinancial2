export const ENQUEUE_MODE_AUTO_VALIDATED_AI = "auto_validated_ai";
export const ENQUEUE_MODE_MANUAL_REVIEW_QUEUE = "manual_review_queue";

export const postingQueueEnqueueModeValues = [ENQUEUE_MODE_AUTO_VALIDATED_AI, ENQUEUE_MODE_MANUAL_REVIEW_QUEUE] as const;

export type PostingQueueEnqueueMode = (typeof postingQueueEnqueueModeValues)[number];

export function isAutoValidatedAiEnqueueMode(enqueueMode: string | null | undefined): boolean {
  return enqueueMode === ENQUEUE_MODE_AUTO_VALIDATED_AI;
}

export function getPostingQueueHandoffModeLabel(enqueueMode: string | null | undefined): string {
  return isAutoValidatedAiEnqueueMode(enqueueMode) ? "auto-validated AI" : "manual queue";
}

export function getPostingQueueActivityLineageLabel(enqueueMode: string | null | undefined): string {
  return isAutoValidatedAiEnqueueMode(enqueueMode) ? "auto-validated AI draft" : "manual review queue";
}

export function getPostingQueueDetailLineageText(enqueueMode: string | null | undefined): string {
  return isAutoValidatedAiEnqueueMode(enqueueMode)
    ? "Linked to an auto-validated AI draft in the accounting copilot flow."
    : "Linked to a manual review queue draft.";
}
