export const POSTING_QUEUE_STATUS_PENDING_REVIEW = "pending_review";
export const POSTING_QUEUE_STATUS_APPROVED = "approved";
export const POSTING_QUEUE_STATUS_REJECTED = "rejected";

export const postingQueueStatusValues = [
  POSTING_QUEUE_STATUS_PENDING_REVIEW,
  POSTING_QUEUE_STATUS_APPROVED,
  POSTING_QUEUE_STATUS_REJECTED,
] as const;

export type PostingQueueStatus = (typeof postingQueueStatusValues)[number];

export type PostingQueueReviewAction = Exclude<PostingQueueStatus, typeof POSTING_QUEUE_STATUS_PENDING_REVIEW>;
