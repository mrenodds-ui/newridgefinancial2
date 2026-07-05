/**
 * HAL staff consent — pending outbound actions and grant flow.
 */
const HalConsent = (function () {
  const STORAGE_KEY = "halConsentState";
  const CONSENT_PHRASES = /^(i consent|yes[, ]? i consent|confirmed[, ]? proceed|proceed with consent|go ahead)$/i;

  const ROLE_POLICY = {
    staff: { email: true, "qb-export": true, "qbo-post": false, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": false },
    office_manager: { email: true, "qb-export": true, "qbo-post": true, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true },
    owner: { email: true, "qb-export": true, "qbo-post": true, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true },
  };
  const DEFAULT_ROLE = "office_manager";

  let pending = null;

  function getRolePolicy(role) {
    const key = String(role || DEFAULT_ROLE).toLowerCase().replace(/\s+/g, "_");
    return ROLE_POLICY[key] || ROLE_POLICY[DEFAULT_ROLE];
  }

  function roleAllows(kind, role) {
    const policy = getRolePolicy(role);
    if (!kind) return true;
    return policy[kind] !== false;
  }

  function outboundKind(query, intent) {
    const q = String(query || "").toLowerCase();
    const it = String(intent || "").toLowerCase();
    if (it === "capability:consent-required" || it === "consent: required") return detectKindFromText(q);
    if (/\b(email|e-?mail)\b.*\b(payer|insurance|patient|staff)\b|\b(payer|insurance)\b.*\b(email|contact)\b/.test(q)) return "email";
    if (/\b(qbo api|quickbooks online)\b.*\bpost\b|\bpost\b.*\b(qbo api|quickbooks online)\b/.test(q)) return "qbo-post";
    if (/\bpost(ing)?\s+to\s+quickbooks\b|\bquickbooks\s+post\b|\bexport.*(approved|posting|journal)\b/.test(q)) return "qb-export";
    if (/\b(upload|portal)\b.*\bnarrative\b|\bnarrative\b.*\b(upload|portal)\b/.test(q)) return "narrative-portal";
    if (/\b(payer portal rpa|portal rpa|rpa prep)\b/.test(q)) return "payer-portal-rpa";
    if (/\bwrite\s*(back|back)\s*to\s*softdent\b|\bsoftdent\s*write\b/.test(q)) return "softdent-writeback";
    if (/\bsubmit\b.*\b(claim|payer|portal)\b|\b(claim|payer)\b.*\bsubmit\b/.test(q)) return "claim-submit";
    if (/\b(fax|upload|transmit)\b/.test(q)) return "delivery";
    return null;
  }

  function detectKindFromText(text) {
    const q = String(text || "").toLowerCase();
    if (/\bemail|e-?mail\b/.test(q)) return "email";
    if (/\b(qbo api|quickbooks online)\b.*\bpost\b|\bpost\b.*\b(qbo api|quickbooks online)\b/.test(q)) return "qbo-post";
    if (/\bpost\b.*\bquickbooks\b|\bquickbooks\b.*\bpost\b|\bexport\b.*\b(journal|posting|approved)\b/.test(q)) return "qb-export";
    if (/\b(upload|portal)\b.*\bnarrative\b|\bnarrative\b.*\b(upload|portal)\b/.test(q)) return "narrative-portal";
    if (/\b(payer portal rpa|portal rpa|rpa prep)\b/.test(q)) return "payer-portal-rpa";
    if (/\bwrite\s*(back|back)\s*to\s*softdent\b|\bsoftdent\s*write\b/.test(q)) return "softdent-writeback";
    if (/\bsubmit\b.*\bclaim\b|\bclaim\b.*\bsubmit\b/.test(q)) return "claim-submit";
    return "delivery";
  }

  function parseEmailDraft(query, context) {
    const q = String(query || "");
    const toMatch = q.match(/\bto\s+([^\n,;]+@[^\s,;]+)/i) || q.match(/([^\s,;]+@[^\s,;]+)/);
    const claimMatch = q.match(/\bclaim\s+([A-Z0-9-]+)/i);
    const subject = claimMatch ? `Claim follow-up ${claimMatch[1]}` : "Practice follow-up from New Ridge Family Dental";
    const body =
      (context && context.draftBody) ||
      `Staff-requested follow-up regarding ${claimMatch ? `claim ${claimMatch[1]}` : "the referenced item"}. Please review before sending.`;
    return {
      to: toMatch ? toMatch[1].trim() : "",
      subject,
      body,
      claimId: claimMatch ? claimMatch[1] : null,
    };
  }

  function setPending(action) {
    pending = action && typeof action === "object" ? Object.assign({ createdAt: new Date().toISOString() }, action) : null;
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageSet) {
      DesktopBridge.storageSet(STORAGE_KEY, pending).catch(() => {});
    }
  }

  async function loadPending() {
    if (pending) return pending;
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageGet) {
      try {
        pending = await DesktopBridge.storageGet(STORAGE_KEY);
      } catch {
        pending = null;
      }
    }
    return pending;
  }

  function clearPending() {
    pending = null;
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageSet) {
      DesktopBridge.storageSet(STORAGE_KEY, null).catch(() => {});
    }
  }

  function isConsentPhrase(query) {
    return CONSENT_PHRASES.test(String(query || "").trim());
  }

  function isCancelPhrase(query) {
    return /^(cancel|never mind|stop|don't|do not proceed)$/i.test(String(query || "").trim());
  }

  function tryStandingConsent(kind, halModels) {
    if (typeof HalEmployee === "undefined" || !HalEmployee.standingAllows) return null;
    if (!HalEmployee.standingAllows(kind, halModels)) return null;
    return HalEmployee.standingConsentText(halModels);
  }

  function createPendingFromQuery(query, intent, extra) {
    const kind = outboundKind(query, intent) || "delivery";
    const draft = kind === "email" ? parseEmailDraft(query, extra) : null;
    const action = {
      kind,
      query: String(query || ""),
      intent: String(intent || ""),
      draft,
      summary:
        kind === "email"
          ? `Email${draft && draft.to ? ` to ${draft.to}` : ""}${draft && draft.subject ? `: ${draft.subject}` : ""}`
          : kind === "qb-export"
            ? "Export approved journal entries to QuickBooks IIF"
            : kind === "qbo-post"
              ? "Post approved journal entries to QuickBooks Online API"
              : kind === "claim-submit"
              ? "Build claim submission packet for payer portal upload"
              : kind === "narrative-portal"
                ? "Prepare narrative text for payer portal upload"
                : kind === "payer-portal-rpa"
                  ? "Build payer portal RPA prep bundle (staff confirms submit)"
                  : kind === "softdent-writeback"
                    ? "Queue SoftDent writeback (consent-gated)"
                    : "Outbound delivery",
    };
    setPending(action);
    return action;
  }

  function followUpChips(pendingAction) {
    if (!pendingAction) return [];
    const chips = [{ label: "I consent", query: "I consent", consent: true }];
    if (pendingAction.kind === "email" && pendingAction.draft && !pendingAction.draft.to) {
      chips.unshift({ label: "Add recipient email", query: "Email payer at billing@example.com about this claim" });
    }
    if (pendingAction.kind === "qb-export" || pendingAction.kind === "qbo-post") {
      chips.unshift({ label: "Show posting queue", query: "Show journal posting queue" });
    }
    if (pendingAction.kind === "claim-submit" || pendingAction.kind === "narrative-portal") {
      chips.unshift({ label: "Open Claims", query: "Open claims workbench", action: { type: "openPage", page: "claims" } });
    }
    chips.push({ label: "Cancel", query: "Cancel", cancel: true });
    return chips;
  }

  function wrapReplyWithConsent(text, pendingAction) {
    const body = String(text || "").trim();
    if (!pendingAction) return body;
    return `${body}\n\nPending: ${pendingAction.summary}. Tap **I consent** or say "I consent" when you are ready.`;
  }

  return {
    outboundKind,
    tryStandingConsent,
    getRolePolicy,
    roleAllows,
    isConsentPhrase,
    isCancelPhrase,
    createPendingFromQuery,
    setPending,
    loadPending,
    clearPending,
    getPending: () => pending,
    followUpChips,
    wrapReplyWithConsent,
    parseEmailDraft,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalConsent;
}
if (typeof window !== "undefined") {
  window.HalConsent = HalConsent;
}
