import { useQuery } from "@tanstack/react-query";

import { fetchClaimPacketReadiness } from "../../api/client";

const LOCAL_SAFETY_BADGES = [
  "Local-Only",
  "Read-Only Sources",
  "Human Review Required",
  "Not Submitted",
] as const;

const EXTERNAL_FIREWALL_LABELS = [
  "No Email",
  "No Fax",
  "No Upload",
  "No Payer Contact",
  "No SoftDent Writeback",
  "No Cloud Fallback",
  "No 235B",
] as const;

const WORK_SURFACES = [
  "Priorities review surface",
  "Office task surface",
  "Draft review surface",
  "Claim packet review surface",
  "Claim follow-up surface",
  "Patient prep surface",
] as const;

type SourceIntakeCard = {
  id: string;
  label: string;
  status: string;
  available: boolean;
};

type ReadinessLane = {
  key: "ready" | "needs-review" | "blocked";
  title: string;
  count: number;
  note: string;
};

export function HalControlTower({
  arAvailable,
  claimsAvailable,
  openTaskCount,
  draftsAwaitingReview,
  packetsReady,
}: {
  arAvailable: boolean;
  claimsAvailable: boolean;
  openTaskCount: number;
  draftsAwaitingReview: number;
  packetsReady: number;
}) {
  const readinessQuery = useQuery({
    queryKey: ["claim-packet-readiness"],
    queryFn: fetchClaimPacketReadiness,
  });
  const summary = readinessQuery.data?.summary;
  const readyCount = summary?.ready_count ?? 0;
  const needsReviewCount = summary?.needs_review_count ?? 0;
  const blockedCount = summary?.blocked_count ?? 0;
  const totalPackets = summary?.total_count ?? 0;

  const sourceCards: SourceIntakeCard[] = [
    {
      id: "ar",
      label: "SoftDent DAYSHEET A/R",
      status: arAvailable ? "Imported (read-only)" : "Awaiting import",
      available: arAvailable,
    },
    {
      id: "claims",
      label: "SoftDent claims export",
      status: claimsAvailable ? "Imported (read-only)" : "Awaiting import",
      available: claimsAvailable,
    },
    {
      id: "tasks",
      label: "Local office tasks",
      status: openTaskCount > 0 ? `${openTaskCount} open` : "None open",
      available: openTaskCount > 0,
    },
    {
      id: "packets",
      label: "Local packets prepared",
      status: packetsReady > 0 ? `${packetsReady} ready for internal use` : "None prepared",
      available: packetsReady > 0,
    },
  ];

  const lanes: ReadinessLane[] = [
    { key: "ready", title: "Ready lane", count: readyCount, note: "Packets with verified local facts" },
    {
      key: "needs-review",
      title: "Needs-review lane",
      count: needsReviewCount,
      note: "Awaiting staff review before use",
    },
    { key: "blocked", title: "Blocked lane", count: blockedCount, note: "Missing facts block local use" },
  ];

  return (
    <section className="hal-control-tower" aria-labelledby="hal-control-tower-title">
      <div className="hal-control-tower__head">
        <p className="eyebrow">Command center</p>
        <h2 id="hal-control-tower-title">Local Claim Intelligence Control Tower</h2>
        <p>
          A read-only operating picture of HAL&apos;s local reasoning. Sources flow in on the left, HAL reasons in the
          center, and staff work surfaces stay review-only. Nothing leaves this machine.
        </p>
      </div>

      <div className="hal-control-tower__badges" aria-label="Local safety posture">
        {LOCAL_SAFETY_BADGES.map((badge) => (
          <span key={badge} className="hal-control-tower__badge">
            {badge}
          </span>
        ))}
      </div>

      <div className="hal-control-tower__grid">
        <div className="hal-control-tower__column" aria-labelledby="hal-control-tower-intake-title">
          <h3 id="hal-control-tower-intake-title" className="hal-control-tower__column-title">
            Read-only source intake
          </h3>
          <ul className="hal-control-tower__intake-list">
            {sourceCards.map((card) => (
              <li
                key={card.id}
                className={`hal-control-tower__intake-card hal-control-tower__intake-card--${
                  card.available ? "live" : "waiting"
                }`}
              >
                <span className="hal-control-tower__intake-label">{card.label}</span>
                <span className="hal-control-tower__intake-status">{card.status}</span>
                <span className="hal-control-tower__intake-tag" aria-hidden="true">
                  Read-only
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="hal-control-tower__column hal-control-tower__column--core">
          <div className="hal-control-tower__core" aria-label="HAL local reasoning core">
            <span className="hal-control-tower__core-eyebrow">HAL local reasoning</span>
            <strong className="hal-control-tower__core-count">{totalPackets}</strong>
            <span className="hal-control-tower__core-label">Claim packets in readiness view</span>
            {readinessQuery.isPending ? (
              <span className="hal-control-tower__core-note">Loading local readiness...</span>
            ) : null}
            {readinessQuery.isError ? (
              <span className="hal-control-tower__core-note" role="alert">
                Local readiness is temporarily unavailable.
              </span>
            ) : null}
          </div>
          <div className="hal-control-tower__lanes" aria-label="Claim packet readiness lanes">
            {lanes.map((lane) => (
              <div
                key={lane.key}
                className={`hal-control-tower__lane hal-control-tower__lane--${lane.key}`}
              >
                <span className="hal-control-tower__lane-title">{lane.title}</span>
                <strong className="hal-control-tower__lane-count">{lane.count}</strong>
                <span className="hal-control-tower__lane-note">{lane.note}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="hal-control-tower__column" aria-labelledby="hal-control-tower-surfaces-title">
          <h3 id="hal-control-tower-surfaces-title" className="hal-control-tower__column-title">
            Staff work surfaces
          </h3>
          <ul className="hal-control-tower__surface-list">
            {WORK_SURFACES.map((surface) => (
              <li key={surface} className="hal-control-tower__surface-item">
                {surface}
              </li>
            ))}
          </ul>
          <p className="hal-control-tower__surface-note">
            {draftsAwaitingReview > 0
              ? `${draftsAwaitingReview} draft(s) awaiting human review`
              : "No drafts awaiting review yet"}
          </p>
        </div>
      </div>

      <div className="hal-control-tower__firewall" aria-label="External action firewall">
        <span className="hal-control-tower__firewall-title">External action firewall</span>
        <ul className="hal-control-tower__firewall-list">
          {EXTERNAL_FIREWALL_LABELS.map((label) => (
            <li key={label} className="hal-control-tower__firewall-chip" aria-disabled="true">
              {label}
            </li>
          ))}
        </ul>
        <p className="hal-control-tower__firewall-note">
          These external actions are blocked by design. HAL prepares local drafts only.
        </p>
      </div>
    </section>
  );
}
