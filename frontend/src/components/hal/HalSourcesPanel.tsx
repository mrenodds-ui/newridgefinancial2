import type { HalAskResponse } from "../../api/schemas";

const SENSITIVE_PATTERNS = [
  /\b\d{3}-\d{2}-\d{4}\b/g,
  /\b(?:mrn|ssn|dob|password|api[_ -]?key|secret)\s*[:#=]?\s*[\w.-]+/gi,
  /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/g,
];

function looksLikeRawCsv(value: string) {
  const firstLine = value.split(/\r?\n/)[0] ?? "";
  const commaCount = (firstLine.match(/,/g) ?? []).length;
  const headerish = /patient|claim|mrn|ssn|dob|payer|procedure/i.test(firstLine);
  return commaCount >= 3 && headerish;
}

export function sanitizeSourceExcerpt(value: string) {
  if (looksLikeRawCsv(value)) {
    return "Bounded source summary only. Raw CSV-like content was hidden.";
  }
  return SENSITIVE_PATTERNS.reduce((text, pattern) => text.replace(pattern, "[REDACTED]"), value);
}

function groupLabel(category: string, title: string) {
  const joined = `${category} ${title}`.toLowerCase();
  if (joined.includes("clinical")) return "Clinical notes";
  if (joined.includes("claim")) return "SoftDent claims";
  if (joined.includes("ledger") || joined.includes("a/r")) return "Ledger / A/R";
  if (joined.includes("payer")) return "Payer / claim status";
  if (joined.includes("memory") || joined.includes("knowledge")) return "Knowledge memory";
  if (joined.includes("runtime") || joined.includes("hardware")) return "Runtime checks";
  if (joined.includes("unavailable") || joined.includes("missing")) return "Unavailable data";
  return "Other bounded sources";
}

export function HalSourcesPanel({ response }: { response: HalAskResponse | undefined }) {
  const grouped = new Map<string, NonNullable<HalAskResponse["retrieved_context"]>>();
  for (const item of response?.retrieved_context ?? []) {
    const label = groupLabel(item.category, item.title);
    grouped.set(label, [...(grouped.get(label) ?? []), item]);
  }

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-sources-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">What HAL looked at</p>
        <h2 id="hal-sources-title">Bounded source summaries</h2>
        <p>HAL shows summaries only. Raw CSV/database dumps and sensitive identifiers are not displayed here.</p>
      </div>
      {grouped.size === 0 ? <p>No supporting source details were needed for the latest answer.</p> : null}
      {[...grouped.entries()].map(([label, items]) => (
        <div key={label} className="hal-source-group">
          <h3>{label}</h3>
          {items.map((item) => (
            <div key={item.source_id} className="hal-supporting-context-item">
              <strong>{item.title}</strong>
              <p>{sanitizeSourceExcerpt(item.excerpt)}</p>
            </div>
          ))}
        </div>
      ))}
      {(response?.governance_notes ?? []).length ? (
        <div className="hal-source-group">
          <h3>Governance and memory</h3>
          {response?.governance_notes.map((item) => (
            <p key={`${item.label}-${item.detail}`}>
              <strong>{item.label}:</strong> {item.detail}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
