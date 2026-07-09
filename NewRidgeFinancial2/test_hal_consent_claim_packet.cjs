/**
 * Smoke: HalConsent stages claim-packet drafts with claimId for appeal finish-line.
 */
const path = require("path");
const assert = require("assert");

const consentPath = path.join(__dirname, "site", "hal-consent.js");
// Load as CommonJS via module.exports
const HalConsent = require(consentPath);

assert.strictEqual(typeof HalConsent.createPendingClaimPacket, "function");
assert.strictEqual(typeof HalConsent.parseClaimPacketDraft, "function");

const pending = HalConsent.createPendingClaimPacket({
  claimId: "DS-20260709-1",
  narrative: "Denial appeal draft",
  payer: "Delta Dental",
  gaps: ["Attachments not confirmed ready"],
});
assert.strictEqual(pending.kind, "claim-submit");
assert.strictEqual(pending.draft.claimId, "DS-20260709-1");
assert.ok(String(pending.summary).includes("DS-20260709-1"));
assert.strictEqual(HalConsent.getPending().draft.claimId, "DS-20260709-1");

const fromQuery = HalConsent.createPendingFromQuery(
  "Build claim packet zip for CLM-99 with consent",
  "claim-submit",
  { narrative: "n1", payer: "MetLife" },
);
assert.strictEqual(fromQuery.kind, "claim-submit");
assert.strictEqual(fromQuery.draft.claimId, "CLM-99");

const kind = HalConsent.outboundKind("build claim packet zip for DS-1 with consent", "");
assert.strictEqual(kind, "claim-submit");

console.log("test_hal_consent_claim_packet: ok");
