import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";

import { fetchLocalAccountingDocuments } from "../api/client";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";

function humanizeCorrectionFlag(flag: string) {
  return flag.replaceAll("_", " ");
}

function confidenceBadgeClass(label: string, reviewRequired: boolean) {
  if (label === "manual review") {
    return "dashboard-import-status-badge dashboard-import-status-badge--error";
  }
  if (reviewRequired || label === "review suggested") {
    return "dashboard-import-status-badge dashboard-import-status-badge--pending";
  }
  return "dashboard-import-status-badge";
}

function buildCorrectionFlags(item: {
  correction_flags?: string[];
  vendor_name: string | null;
  invoice_number: string | null;
  document_date: string | null;
  raw_text: string;
}) {
  if (item.correction_flags?.length) {
    return item.correction_flags.map(humanizeCorrectionFlag);
  }
  const flags: string[] = [];
  const rawUpper = item.raw_text.toUpperCase();
  if (item.vendor_name && !rawUpper.includes(item.vendor_name.toUpperCase())) {
    flags.push("vendor normalized");
  }
  if (item.invoice_number && !rawUpper.includes(item.invoice_number.toUpperCase())) {
    flags.push("invoice corrected");
  }
  if (item.document_date && !rawUpper.includes(item.document_date.toUpperCase())) {
    flags.push("date corrected");
  }
  return flags;
}

function buildConfidenceLabel(item: {
  extractor: string;
  raw_text: string;
  vendor_name: string | null;
  invoice_number: string | null;
  document_date: string | null;
}) {
  const corrections = buildCorrectionFlags(item).length;
  if (item.extractor === "plain_text" || item.extractor === "pdf_text") {
    return { label: "high confidence", tone: "ok" };
  }
  if (corrections === 0 && item.raw_text.length > 40) {
    return { label: "medium confidence", tone: "ok" };
  }
  if (corrections <= 2) {
    return { label: "review suggested", tone: "warning" };
  }
  return { label: "manual review", tone: "critical" };
}

function formatCurrency(value: number | null, currency: string | null | undefined) {
  if (value === null || !Number.isFinite(value)) {
    return "Unavailable";
  }

  const normalizedCurrency = typeof currency === "string" ? currency.trim().toUpperCase() : "";
  if (!/^[A-Z]{3}$/.test(normalizedCurrency)) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: normalizedCurrency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }
}

export default function AccountingDocumentsPage() {
  const [search, setSearch] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const documentsQuery = useQuery({
    queryKey: ["accounting-documents-page", deferredSearch, documentType, reviewOnly],
    queryFn: () =>
      fetchLocalAccountingDocuments({
        limit: 25,
        search: deferredSearch.trim() || undefined,
        documentType: documentType || undefined,
        reviewOnly,
      }),
  });

  const summary = useMemo(() => {
    const items = documentsQuery.data?.items ?? [];
    const totalDocuments = items.length;
    const invoiceCount = items.filter((item) => item.document_type === "invoice").length;
    const receiptCount = items.filter((item) => item.document_type === "receipt").length;
    const needsReviewCount = items.filter((item) => item.review_required).length;
    const highConfidenceCount = items.filter((item) => item.confidence_label === "high confidence").length;
    const reviewSuggestedCount = items.filter((item) => item.confidence_label === "review suggested").length;
    const totalValue = items.reduce((sum, item) => sum + (item.total_amount ?? 0), 0);
    return {
      totalDocuments,
      invoiceCount,
      receiptCount,
      needsReviewCount,
      highConfidenceCount,
      reviewSuggestedCount,
      totalValue,
    };
  }, [documentsQuery.data]);

  return (
    <PageSurfaceShell className="accounting-documents-page">
      <PageSurfaceHeader
        breadcrumbs="Accounting / OCR ledger"
        eyebrow="Accounting OCR"
        title="Accounting documents"
        titleId="accounting-documents-title"
        description="Local OCR ledger for invoices, receipts, and statements that HAL can search and reference."
        badges={[
          { label: "Local-Only" },
          { label: "Human Review Required" },
          { label: "No Upload" },
        ]}
        statusItems={[
          { label: "Visible documents", value: String(summary.totalDocuments) },
          { label: "Needs review", value: String(summary.needsReviewCount) },
          { label: "Visible total", value: formatCurrency(summary.totalValue, "USD") },
        ]}
      />

      <div className="kpi-grid">
        <div className="hal-answer-card">
          <h2>Documents</h2>
          <div>{summary.totalDocuments}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Invoices</h2>
          <div>{summary.invoiceCount}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Receipts</h2>
          <div>{summary.receiptCount}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Needs Review</h2>
          <div>{summary.needsReviewCount}</div>
        </div>
        <div className="hal-answer-card">
          <h2>High Confidence</h2>
          <div>{summary.highConfidenceCount}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Review Suggested</h2>
          <div>{summary.reviewSuggestedCount}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Visible Total</h2>
          <div>{formatCurrency(summary.totalValue, "USD")}</div>
        </div>
      </div>

      <section className="hal-answer-card">
        <h2>Search OCR Ledger</h2>
        <form className="hal-form hal-form--narrative" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="accounting-documents-search">Search</label>
          <input
            id="accounting-documents-search"
            className="hal-form__textarea"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Vendor, invoice number, filename, or extracted text"
          />
          <label htmlFor="accounting-documents-type">Document type</label>
          <select
            id="accounting-documents-type"
            className="hal-form__textarea"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value)}
          >
            <option value="">All types</option>
            <option value="invoice">Invoice</option>
            <option value="receipt">Receipt</option>
            <option value="bank_statement">Bank statement</option>
            <option value="financial_document">Financial document</option>
          </select>
          <label htmlFor="accounting-documents-review-only">Needs review only</label>
          <input
            id="accounting-documents-review-only"
            type="checkbox"
            checked={reviewOnly}
            onChange={(event) => setReviewOnly(event.target.checked)}
          />
        </form>

        {documentsQuery.isPending ? <div className="hal-answer-card__section">Loading accounting documents...</div> : null}
        {documentsQuery.isError ? (
          <div className="hal-answer-card__section">
            {documentsQuery.error instanceof Error ? documentsQuery.error.message : "Unable to load accounting documents."}
          </div>
        ) : null}

        {documentsQuery.data ? (
          <div className="dashboard-import-history">
            <table className="import-history-table">
              <thead>
                <tr>
                  <th>Vendor / File</th>
                  <th>Invoice</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Total</th>
                  <th>Extractor</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {documentsQuery.data.items.map((item) => {
                  const confidence = item.confidence_label
                    ? {
                        label: item.confidence_label,
                        tone: item.review_required ? "warning" : "ok",
                      }
                    : buildConfidenceLabel(item);
                  return (
                    <tr key={item.id}>
                      <td>{item.vendor_name || item.source_name}</td>
                      <td>{item.invoice_number || item.source_name}</td>
                      <td>{item.document_type}</td>
                      <td>{item.document_date || "Unavailable"}</td>
                      <td>{formatCurrency(item.total_amount, item.currency)}</td>
                      <td>{item.extractor}</td>
                      <td>
                        <span className={confidenceBadgeClass(confidence.label, item.review_required)}>{confidence.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {documentsQuery.data.items.length === 0 ? (
              <div className="hal-answer-card__section">No OCR documents matched your filters.</div>
            ) : null}
          </div>
        ) : null}
      </section>

      {documentsQuery.data?.items.length ? (
        <section className="hal-answer-card">
          <h2>Normalized Vs Raw OCR</h2>
          {documentsQuery.data.items.map((item) => (
            <div key={`preview-${item.id}`} className="hal-supporting-context-item">
              <strong>{item.vendor_name || item.source_name}</strong>
              <div>
                <span className={confidenceBadgeClass(item.confidence_label || buildConfidenceLabel(item).label, item.review_required)}>
                  {item.confidence_label || buildConfidenceLabel(item).label}
                </span>
              </div>
              <div>
                {buildCorrectionFlags(item).map((flag) => (
                  <span
                    key={`${item.id}-${flag}`}
                    className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced"
                  >
                    {flag}
                  </span>
                ))}
                {buildCorrectionFlags(item).length === 0 ? <span className="dashboard-import-status-badge">no corrections</span> : null}
              </div>
              <div>
                <strong>Normalized:</strong> {item.invoice_number || item.source_name} · {item.document_date || "Unavailable"} ·{" "}
                {formatCurrency(item.total_amount, item.currency)}
              </div>
              <div>
                <strong>Preview:</strong> {item.text_preview}
              </div>
              <div>
                <strong>Raw OCR:</strong> {item.raw_text || item.text_preview}
              </div>
            </div>
          ))}
        </section>
      ) : null}
    </PageSurfaceShell>
  );
}
