import type { ReactNode } from "react";
import type { HalAskResponse } from "../../api/schemas";

type HalRecommendationBlockProps = {
  response: HalAskResponse | undefined;
  reviewDepth: "primary" | "second_opinion";
  speechControls?: ReactNode;
};

function splitAnswer(answer: string) {
  const sections = {
    practical: answer,
    sourceBasis: "",
    recommendation: "",
    missingData: "",
    followUp: "",
    approval: "",
  };
  const sentences = answer.split(/(?<=\.)\s+/).filter(Boolean);
  sections.practical = sentences[0] ?? answer;
  sections.sourceBasis = sentences
    .filter((item) => /source|context|verified|softdent|quickbooks|runtime/i.test(item))
    .slice(0, 2)
    .join(" ");
  sections.recommendation = sentences.find((item) => /recommend|next|should|prepare|review/i.test(item)) ?? "";
  sections.missingData = sentences.filter((item) => /missing|unavailable|not available/i.test(item)).join(" ");
  sections.followUp = sentences.find((item) => /\?$|follow-up|follow up/i.test(item)) ?? "";
  sections.approval = sentences.filter((item) => /approval|review required|human review|draft|not submitted/i.test(item)).join(" ");
  return sections;
}

export function HalRecommendationBlock({ response, reviewDepth, speechControls }: HalRecommendationBlockProps) {
  if (!response) {
    return (
      <section className="hal-workstation-card" aria-labelledby="hal-recommendation-title">
        <p className="eyebrow">Recommendation / next step</p>
        <h2 id="hal-recommendation-title">HAL is ready for the next office question.</h2>
        <p>Ask HAL to review a patient, claim, missing documentation, payer status, or today&apos;s practice priorities.</p>
      </section>
    );
  }

  const sections = splitAnswer(response.answer);
  return (
    <section className="hal-workstation-card" aria-labelledby="hal-recommendation-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Recommendation / next step</p>
        <h2 id="hal-recommendation-title">HAL&apos;s Response</h2>
        <p>
          Staff-assistant response ·{" "}
          Review depth: {reviewDepth === "second_opinion" ? "Deeper second opinion" : "Primary response"} ·{" "}
          {response.voice_profile.label}
        </p>
      </div>
      <div className="hal-recommendation-grid">
        <section>
          <h3>Practical answer</h3>
          <p>{sections.practical}</p>
        </section>
        <section>
          <h3>Reason / source basis</h3>
          <p>{sections.sourceBasis || "See What HAL Looked At for bounded supporting sources."}</p>
        </section>
        <section>
          <h3>Recommendation</h3>
          <p>{sections.recommendation || "Use the answer above as the current staff recommendation."}</p>
        </section>
        <section>
          <h3>Missing data</h3>
          <p>{sections.missingData || "No missing data was called out in this answer."}</p>
        </section>
        <section>
          <h3>Follow-up question</h3>
          <p>{sections.followUp || "No follow-up question is required yet."}</p>
        </section>
        <section>
          <h3>Human approval needed</h3>
          <p>{sections.approval || "Any draft, packet, or operational action still needs human review before use."}</p>
        </section>
      </div>
      <div className="hal-answer-card__section hal-answer-card__section--lead">{response.answer}</div>
      {speechControls}
      <div className="hal-answer-card__section">
        <strong>Reference ID:</strong> {response.audit_id}
      </div>
    </section>
  );
}
