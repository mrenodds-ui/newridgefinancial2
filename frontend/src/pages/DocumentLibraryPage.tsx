import { useMutation, useQuery } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useDeferredValue, useState } from "react";

import { askDocumentRagQuestion, fetchDocumentRagDocuments, uploadDocumentRagDocument } from "../api/client";
import { queryClient } from "../queryClient";

const DOCUMENT_LIBRARY_MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const DOCUMENT_LIBRARY_ALLOWED_EXTENSIONS = new Set(["pdf", "txt", "md", "csv", "json"]);

function formatTimestamp(value: string) {
  if (!value) {
    return "Unavailable";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function formatCount(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function humanizeGuardrail(flag: string) {
  switch (flag) {
    case "uploaded files only":
      return "Uses only the uploaded file library";
    case "grounded answer only":
      return "Answers only from retrieved file context";
    case "insufficient context fallback":
      return "Falls back instead of inventing missing facts";
    case "audit log recorded":
      return "Records an audit trail";
    default:
      return flag;
  }
}

export default function DocumentLibraryPage() {
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(4);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadInputKey, setUploadInputKey] = useState(0);
  const [uploadSelectionError, setUploadSelectionError] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);

  const documentsQuery = useQuery({
    queryKey: ["document-rag-documents", deferredSearch],
    queryFn: () =>
      fetchDocumentRagDocuments({
        limit: 25,
        search: deferredSearch.trim() || undefined,
      }),
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocumentRagDocument,
    onSuccess: async () => {
      setSelectedFile(null);
      setUploadSelectionError(null);
      setUploadInputKey((current) => current + 1);
      await queryClient.invalidateQueries({
        queryKey: ["document-rag-documents"],
      });
    },
  });

  const askMutation = useMutation({
    mutationFn: ({ nextQuestion, nextTopK }: { nextQuestion: string; nextTopK: number }) =>
      askDocumentRagQuestion(nextQuestion, { topK: nextTopK }),
  });

  const documents = documentsQuery.data?.items ?? [];
  const totalPages = documents.reduce((sum, item) => sum + item.page_count, 0);
  const totalChunks = documents.reduce((sum, item) => sum + item.chunk_count, 0);
  const totalCharacters = documents.reduce((sum, item) => sum + item.content_char_count, 0);

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile || uploadMutation.isPending || uploadSelectionError) {
      return;
    }
    uploadMutation.mutate(selectedFile);
  }

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setSelectedFile(null);
      setUploadSelectionError(null);
      return;
    }

    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!DOCUMENT_LIBRARY_ALLOWED_EXTENSIONS.has(extension)) {
      setSelectedFile(null);
      setUploadSelectionError("Choose a PDF, TXT, MD, CSV, or JSON file.");
      return;
    }

    if (file.size > DOCUMENT_LIBRARY_MAX_UPLOAD_BYTES) {
      setSelectedFile(null);
      setUploadSelectionError("Choose a file smaller than 25 MB.");
      return;
    }

    setSelectedFile(file);
    setUploadSelectionError(null);
  }

  function handleTopKChange(event: ChangeEvent<HTMLSelectElement>) {
    const parsed = Number(event.target.value);
    setTopK([2, 4, 6, 8].includes(parsed) ? parsed : 4);
  }

  function handleAsk(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || askMutation.isPending) {
      return;
    }
    askMutation.mutate({ nextQuestion: question.trim(), nextTopK: topK });
  }

  return (
    <div className="dashboard-page">
      <h1>Document Library</h1>
      <div className="dashboard-description">
        Upload local 10-Ks, earnings call notes, PDFs, CSV exports, and working notes. HAL chunks them with LangChain, indexes them locally,
        and answers only from retrieved file context.
      </div>

      <div className="kpi-grid">
        <div className="hal-answer-card">
          <h2>Matching Files</h2>
          <div>{documentsQuery.data?.count ?? 0}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Visible Pages</h2>
          <div>{formatCount(totalPages)}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Visible Chunks</h2>
          <div>{formatCount(totalChunks)}</div>
        </div>
        <div className="hal-answer-card">
          <h2>Visible Characters</h2>
          <div>{formatCount(totalCharacters)}</div>
        </div>
      </div>

      <section className="hal-answer-card">
        <h2>Upload Files</h2>
        <div className="hal-answer-card__section hal-answer-card__section--lead">
          Accepted file types: PDF, TXT, MD, CSV, JSON. Uploaded files stay under the local AI workspace document library.
        </div>
        <form className="hal-form hal-form--narrative" onSubmit={handleUpload}>
          <label htmlFor="document-rag-upload">Choose file</label>
          <input
            key={uploadInputKey}
            id="document-rag-upload"
            type="file"
            accept=".pdf,.txt,.md,.csv,.json"
            onChange={handleFileSelection}
          />
          <div className="hal-form__actions">
            <button type="submit" disabled={!selectedFile || uploadMutation.isPending || Boolean(uploadSelectionError)}>
              {uploadMutation.isPending ? "Indexing..." : "Index File"}
            </button>
          </div>
        </form>

        {uploadSelectionError ? <div className="hal-answer-card__section">{uploadSelectionError}</div> : null}

        {uploadMutation.isError ? (
          <div className="hal-answer-card__section">
            {uploadMutation.error instanceof Error ? uploadMutation.error.message : "Unable to index that file."}
          </div>
        ) : null}

        {uploadMutation.data ? (
          <div className="hal-supporting-context-item">
            <strong>{uploadMutation.data.document.source_name}</strong>
            <div>{uploadMutation.data.message}</div>
            <div>
              Stored in the local document library with {uploadMutation.data.document.page_count} page(s) and {uploadMutation.data.document.chunk_count} chunk(s).
            </div>
          </div>
        ) : null}
      </section>

      <section className="hal-answer-card">
        <h2>Ask Grounded Questions</h2>
        <form className="hal-form hal-form--narrative" onSubmit={handleAsk}>
          <label htmlFor="document-rag-question">Question</label>
          <textarea
            id="document-rag-question"
            className="hal-form__textarea"
            rows={5}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about revenue trends, risk factors, guidance, margin changes, covenant language, or any uploaded note."
          />
          <label htmlFor="document-rag-top-k">Retrieved chunks</label>
          <select id="document-rag-top-k" className="hal-form__textarea" value={String(topK)} onChange={handleTopKChange}>
            <option value="2">2 chunks</option>
            <option value="4">4 chunks</option>
            <option value="6">6 chunks</option>
            <option value="8">8 chunks</option>
          </select>
          <div className="hal-form__actions">
            <button type="submit" disabled={!question.trim() || askMutation.isPending}>
              {askMutation.isPending ? "Asking..." : "Ask Document Library"}
            </button>
          </div>
        </form>

        {askMutation.isError ? (
          <div className="hal-answer-card__section">
            {askMutation.error instanceof Error ? askMutation.error.message : "Unable to answer that question."}
          </div>
        ) : null}

        {askMutation.data ? (
          <>
            <div className="hal-answer-card__section hal-answer-card__section--lead">{askMutation.data.answer}</div>
            <div className="hal-answer-card__section">
              <span
                className={
                  askMutation.data.grounded
                    ? "dashboard-import-status-badge"
                    : "dashboard-import-status-badge dashboard-import-status-badge--pending"
                }
              >
                {askMutation.data.grounded ? "grounded" : "insufficient context"}
              </span>
              <span className="dashboard-import-status-badge dashboard-import-status-badge--spaced">
                {askMutation.data.document_count} indexed file(s)
              </span>
            </div>
            {askMutation.data.guardrails.length ? (
              <div className="hal-answer-card__section">
                {askMutation.data.guardrails.map((item) => (
                  <span key={item} className="dashboard-import-status-badge dashboard-import-status-badge--spaced">
                    {humanizeGuardrail(item)}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="hal-answer-card__section">
              <strong>Retrieved context</strong>
            </div>
            {askMutation.data.retrieved_context.map((item) => (
              <div key={item.source_id} className="hal-supporting-context-item">
                <strong>{item.title}</strong>
                <div>{item.excerpt}</div>
              </div>
            ))}
            {askMutation.data.retrieved_context.length === 0 ? (
              <div className="hal-answer-card__section">No supporting snippets were returned for this question.</div>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="hal-answer-card">
        <h2>Indexed Files</h2>
        <form className="hal-form hal-form--narrative" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="document-rag-search">Search indexed file names</label>
          <input
            id="document-rag-search"
            className="hal-form__textarea"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Filter by file name"
          />
        </form>

        {documentsQuery.isPending ? <div className="hal-answer-card__section">Loading indexed files...</div> : null}
        {documentsQuery.isError ? (
          <div className="hal-answer-card__section">
            {documentsQuery.error instanceof Error ? documentsQuery.error.message : "Unable to load indexed files."}
          </div>
        ) : null}

        {documentsQuery.data ? (
          <div className="dashboard-import-history">
            <table className="import-history-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Pages</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((item) => (
                  <tr key={item.document_id}>
                    <td>{item.source_name}</td>
                    <td>{item.mime_type}</td>
                    <td>{formatCount(item.page_count)}</td>
                    <td>{formatCount(item.chunk_count)}</td>
                    <td>{formatTimestamp(item.uploaded_at_utc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {documents.length === 0 ? <div className="hal-answer-card__section">No indexed files matched this filter.</div> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
