/**
 * HAL outbound executors — run email / QB export / claim packets after staff consent.
 */
const HalOutbound = (function () {
  async function loopbackPost(path, payload) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.outboundPost) {
      return DesktopBridge.outboundPost(path, payload || {});
    }
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.hasDesktopApi && DesktopBridge.hasDesktopApi()) {
      const api = window.pywebview && window.pywebview.api;
      if (!api) throw new Error("Desktop API unavailable.");
      if (path === "/api/outbound/email" && api.send_email_with_consent) {
        return api.send_email_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/qb-export" && api.export_posting_queue_iif_with_consent) {
        return api.export_posting_queue_iif_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/claim-packet" && api.build_claim_packet_with_consent) {
        return api.build_claim_packet_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/narrative-prep" && api.export_narrative_portal_prep_with_consent) {
        return api.export_narrative_portal_prep_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/qbo-post" && api.post_qbo_journal_with_consent) {
        return api.post_qbo_journal_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/payer-portal-rpa" && api.build_payer_portal_rpa_with_consent) {
        return api.build_payer_portal_rpa_with_consent(JSON.stringify(payload || {}));
      }
      if (path === "/api/outbound/softdent-writeback" && api.queue_softdent_writeback_with_consent) {
        return api.queue_softdent_writeback_with_consent(JSON.stringify(payload || {}));
      }
    }
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.hasLoopbackApi && DesktopBridge.hasLoopbackApi()) {
      const host = window.location.hostname || "127.0.0.1";
      const port = window.location.port || "8765";
      const resp = await fetch(`${window.location.protocol}//${host}:${port}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
        cache: "no-store",
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.message || err.error || `HTTP ${resp.status}`);
      }
      return resp.json();
    }
    throw new Error("Outbound actions require the NR2 server.");
  }

  async function executePending(pending, consentText) {
    if (!pending || !pending.kind) {
      return { ok: false, message: "No pending outbound action." };
    }
    const consent = String(consentText || "I consent").trim();
    const draft = pending.draft || {};
    if (pending.kind === "email") {
      return loopbackPost("/api/outbound/email", {
        to: draft.to || "",
        subject: draft.subject || "Practice follow-up",
        body: draft.body || pending.query,
        consentText: consent,
        actor: "Staff",
      });
    }
    if (pending.kind === "qb-export") {
      return loopbackPost("/api/outbound/qb-export", { consentText: consent, actor: "Staff", limit: 200 });
    }
    if (pending.kind === "qbo-post") {
      return loopbackPost("/api/outbound/qbo-post", { consentText: consent, actor: "Staff", limit: 25 });
    }
    if (pending.kind === "payer-portal-rpa") {
      return loopbackPost("/api/outbound/payer-portal-rpa", {
        claimId: draft.claimId || "",
        payer: draft.payer || "",
        narrative: draft.body || pending.query,
        consentText: consent,
        actor: "Staff",
      });
    }
    if (pending.kind === "softdent-writeback") {
      return loopbackPost("/api/outbound/softdent-writeback", {
        action: draft.action || "note",
        payload: draft.payload || { text: pending.query },
        consentText: consent,
        actor: "Staff",
      });
    }
    if (pending.kind === "claim-submit") {
      return loopbackPost("/api/outbound/claim-packet", {
        claimId: draft.claimId || "",
        narrative: draft.body || pending.query,
        notes: pending.query,
        consentText: consent,
        actor: "Staff",
      });
    }
    if (pending.kind === "narrative-portal") {
      return loopbackPost("/api/outbound/narrative-prep", {
        claimId: draft.claimId || "",
        narrative: draft.body || pending.query,
        consentText: consent,
        actor: "Staff",
      });
    }
    if (pending.kind === "delivery") {
      return {
        ok: false,
        message: "No executor for this delivery type yet. Try email, claim packet, or QuickBooks export.",
      };
    }
    return { ok: false, message: `No executor for outbound kind "${pending.kind}" yet.` };
  }

  async function fetchQboStatus() {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.quickbooksOnlineStatus) {
      return DesktopBridge.quickbooksOnlineStatus();
    }
    return { ok: false, message: "QuickBooks Online status requires desktop or loopback runtime." };
  }

  function formatResult(result) {
    if (!result) return "Outbound action did not return a result.";
    if (result.message) return result.message;
    if (result.ok && result.exportPath) return `Export ready: ${result.exportPath}`;
    if (result.ok) return "Outbound action completed.";
    return result.error || "Outbound action failed.";
  }

  return {
    executePending,
    formatResult,
    fetchQboStatus,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalOutbound;
}
if (typeof window !== "undefined") {
  window.HalOutbound = HalOutbound;
}
