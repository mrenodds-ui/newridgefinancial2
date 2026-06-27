import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchAccountingPostingQueue, reviewAccountingPostingQueueEntry } from "../api/client";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
import { getPostingQueueDetailLineageText } from "../utils/postingQueueLineage";
import {
  POSTING_QUEUE_STATUS_APPROVED,
  POSTING_QUEUE_STATUS_PENDING_REVIEW,
  POSTING_QUEUE_STATUS_REJECTED,
  type PostingQueueReviewAction,
  type PostingQueueStatus,
} from "../utils/postingQueueStatus";

const postingQueueFilters = [
  { value: "all", label: "All" },
  { value: POSTING_QUEUE_STATUS_PENDING_REVIEW, label: "Pending Review" },
  { value: POSTING_QUEUE_STATUS_APPROVED, label: "Approved" },
  { value: POSTING_QUEUE_STATUS_REJECTED, label: "Rejected" },
] as const;

function isPostingQueueFilterValue(value: string): value is "all" | PostingQueueStatus {
  return postingQueueFilters.some((filter) => filter.value === value);
}

export default function PostingQueueReviewPage() {
  const queryClient = useQueryClient();
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const activeFilterParam = searchParams.get("status") ?? "all";
  const activeFilter = isPostingQueueFilterValue(activeFilterParam) ? activeFilterParam : "all";
  const currentCursor = searchParams.get("cursor") ?? undefined;
  const pageSize = 10;

  const queueQuery = useQuery({
    queryKey: ["accounting-posting-queue", activeFilter, currentCursor],
    queryFn: () =>
      fetchAccountingPostingQueue({
        limit: pageSize,
        cursor: currentCursor,
        status: activeFilter === "all" ? undefined : activeFilter,
      }),
  });

  const reviewMutation = useMutation({
    mutationFn: reviewAccountingPostingQueueEntry,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["accounting-posting-queue"],
      });
    },
  });

  function updateReviewNote(queueId: string, value: string) {
    setReviewNotes((current) => ({ ...current, [queueId]: value }));
  }

  function submitReview(queueId: string, action: PostingQueueReviewAction) {
    reviewMutation.mutate({
      queueId,
      action,
      review_note: reviewNotes[queueId]?.trim() || undefined,
    });
  }

  const items = queueQuery.data?.items ?? [];
  const totalCount = queueQuery.data?.total_count ?? 0;
  const nextCursor = queueQuery.data?.next_cursor ?? null;
  const rangeStart = queueQuery.data?.range_start ?? 0;
  const rangeEnd = queueQuery.data?.range_end ?? 0;
  const hasPreviousPage = cursorHistory.length > 0 || Boolean(currentCursor);
  const hasNextPage = Boolean(nextCursor);

  function setActiveFilter(nextFilter: "all" | PostingQueueStatus) {
    const nextParams = new URLSearchParams(searchParams);
    if (nextFilter === "all") {
      nextParams.delete("status");
    } else {
      nextParams.set("status", nextFilter);
    }
    nextParams.delete("cursor");
    setCursorHistory([]);
    setSearchParams(nextParams, { replace: true });
  }

  function setCursor(nextCursorValue?: string) {
    const nextParams = new URLSearchParams(searchParams);
    if (!nextCursorValue) {
      nextParams.delete("cursor");
    } else {
      nextParams.set("cursor", nextCursorValue);
    }
    setSearchParams(nextParams, { replace: true });
  }

  function goToNextPage() {
    if (!nextCursor) {
      return;
    }
    setCursorHistory((current) => [...current, currentCursor ?? ""]);
    setCursor(nextCursor);
  }

  function goToPreviousPage() {
    if (cursorHistory.length === 0) {
      setCursor(undefined);
      return;
    }

    const previousCursor = cursorHistory[cursorHistory.length - 1];
    setCursorHistory((current) => current.slice(0, -1));
    setCursor(previousCursor || undefined);
  }

  return (
    <PageSurfaceShell className="posting-queue-page">
      <div className="page-content">
        <PageSurfaceHeader
          breadcrumbs="Accounting / Posting queue"
          eyebrow="Accounting copilot"
          title="Posting queue review"
          titleId="posting-queue-title"
          description="Review locally queued QuickBooks Desktop posting drafts. Approval changes queue state only and does not post anything to QuickBooks."
          badges={[
            { label: "Local Queue Only" },
            { label: "No QuickBooks Writeback" },
            { label: "Human Review Required" },
          ]}
          statusItems={[
            { label: "Filter", value: postingQueueFilters.find((f) => f.value === activeFilter)?.label ?? "All" },
            { label: "Visible items", value: String(items.length) },
            { label: "Total queued", value: String(totalCount) },
          ]}
        />

        <div className="posting-queue-filter-row" aria-label="Posting queue filters">
          {postingQueueFilters.map((filter) => (
            <button
              key={filter.value}
              type="button"
              className={activeFilter === filter.value ? "posting-queue-filter posting-queue-filter--active" : "posting-queue-filter"}
              onClick={() => setActiveFilter(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {queueQuery.isLoading ? <div className="hal-answer-card">Loading posting queue...</div> : null}

        {queueQuery.isError ? (
          <div className="hal-answer-card">
            <h2>Queue load failed</h2>
            <div>{queueQuery.error instanceof Error ? queueQuery.error.message : "Unable to load posting queue."}</div>
          </div>
        ) : null}

        {reviewMutation.isError ? (
          <div className="hal-answer-card">
            <h2>Review action failed</h2>
            <div>{reviewMutation.error instanceof Error ? reviewMutation.error.message : "Unable to review queue item."}</div>
          </div>
        ) : null}

        {!queueQuery.isLoading && !queueQuery.isError ? (
          <div className="posting-queue-list">
            {items.length === 0 ? (
              <div className="hal-answer-card">No posting queue items are available for the selected filter.</div>
            ) : null}
            {items.map((item) => {
              const pendingReview = item.status === POSTING_QUEUE_STATUS_PENDING_REVIEW;
              const mutationBusy = reviewMutation.isPending && reviewMutation.variables?.queueId === item.queue_id;
              return (
                <div key={item.queue_id} className="hal-answer-card">
                  <div className="posting-queue-header">
                    <div>
                      <h2>{item.description}</h2>
                      <div className="hal-answer-card__section">
                        <strong>Queue ID:</strong> {item.queue_id}
                      </div>
                    </div>
                    <div className={`posting-queue-status posting-queue-status--${item.status}`}>{item.status.replace("_", " ")}</div>
                  </div>

                  <div className="hal-answer-card__section">
                    <strong>Target system:</strong> {item.target_system}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Source audit:</strong> {item.source_audit_id}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Draft lineage:</strong> {getPostingQueueDetailLineageText(item.enqueue_mode)}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Amount:</strong> {item.amount.toFixed(2)}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Transaction date:</strong> {item.transaction_date}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Accounting period:</strong> {item.accounting_period}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Transaction type:</strong> {item.transaction_type || "Auto-detected"}
                  </div>
                  <div className="hal-answer-card__section">
                    <strong>Validation:</strong> Balanced {item.validation.balanced ? "Yes" : "No"}, open period{" "}
                    {item.validation.open_period ? "Yes" : "No"}
                  </div>

                  <table className="dashboard-import-table">
                    <thead>
                      <tr>
                        <th>Account Code</th>
                        <th>Account Name</th>
                        <th>Debit</th>
                        <th>Credit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.lines.map((line) => (
                        <tr key={`${item.queue_id}-${line.account_code}-${line.account_name}`}>
                          <td>{line.account_code}</td>
                          <td>{line.account_name}</td>
                          <td>{line.debit.toFixed(2)}</td>
                          <td>{line.credit.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {item.reviewed_at_utc ? (
                    <div className="posting-queue-review-meta">
                      <div>
                        <strong>Reviewed by:</strong> {item.reviewer_actor}
                      </div>
                      <div>
                        <strong>Reviewed at:</strong> {item.reviewed_at_utc}
                      </div>
                      {item.review_note ? (
                        <div>
                          <strong>Review note:</strong> {item.review_note}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {pendingReview ? (
                    <div className="posting-queue-review-actions">
                      <label htmlFor={`review-note-${item.queue_id}`}>Review note</label>
                      <textarea
                        id={`review-note-${item.queue_id}`}
                        className="hal-form__textarea"
                        rows={3}
                        value={reviewNotes[item.queue_id] ?? ""}
                        onChange={(event) => updateReviewNote(item.queue_id, event.target.value)}
                        placeholder="Optional reviewer note"
                      />
                      <div className="posting-queue-action-row">
                        <button
                          type="button"
                          className="refresh-button"
                          disabled={mutationBusy}
                          onClick={() => submitReview(item.queue_id, POSTING_QUEUE_STATUS_APPROVED)}
                        >
                          {mutationBusy ? "Saving review..." : "Approve draft"}
                        </button>
                        <button
                          type="button"
                          className="refresh-button posting-queue-button--danger"
                          disabled={mutationBusy}
                          onClick={() => submitReview(item.queue_id, POSTING_QUEUE_STATUS_REJECTED)}
                        >
                          {mutationBusy ? "Saving review..." : "Reject draft"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
            <div className="posting-queue-pagination">
              <button type="button" className="posting-queue-filter" disabled={!hasPreviousPage} onClick={goToPreviousPage}>
                Previous
              </button>
              <div className="posting-queue-pagination__meta">
                Showing {rangeStart}-{rangeEnd} of {totalCount}
              </div>
              <button type="button" className="posting-queue-filter" disabled={!hasNextPage} onClick={goToNextPage}>
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </PageSurfaceShell>
  );
}
