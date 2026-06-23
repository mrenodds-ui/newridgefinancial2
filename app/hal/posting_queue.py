from typing import Literal

ENQUEUE_MODE_AUTO_VALIDATED_AI = "auto_validated_ai"
ENQUEUE_MODE_MANUAL_REVIEW_QUEUE = "manual_review_queue"
POSTING_QUEUE_STATUS_PENDING_REVIEW = "pending_review"
POSTING_QUEUE_STATUS_APPROVED = "approved"
POSTING_QUEUE_STATUS_REJECTED = "rejected"
DRAFT_STATUS_DRAFT_ONLY = "draft_only"
DRAFT_STATUS_ENQUEUED = "enqueued"

PostingQueueEnqueueMode = Literal[
	"auto_validated_ai",
	"manual_review_queue",
]

PostingQueueStatus = Literal[
	"pending_review",
	"approved",
	"rejected",
]

PostingQueueReviewAction = Literal[
	"approved",
	"rejected",
]

JournalDraftStatus = Literal[
	"draft_only",
	"enqueued",
]