export const DRAFT_STATUS_DRAFT_ONLY = "draft_only";
export const DRAFT_STATUS_ENQUEUED = "enqueued";

export const journalDraftStatusValues = [DRAFT_STATUS_DRAFT_ONLY, DRAFT_STATUS_ENQUEUED] as const;

export type JournalDraftStatus = (typeof journalDraftStatusValues)[number];
