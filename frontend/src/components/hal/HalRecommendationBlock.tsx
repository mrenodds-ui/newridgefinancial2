import type { ReactNode } from "react";
import type { HalAskResponse } from "../../api/schemas";

type HalRecommendationBlockProps = {
  response: HalAskResponse | undefined;
  speechControls?: ReactNode;
};

export function HalRecommendationBlock({ response, speechControls }: HalRecommendationBlockProps) {
  if (!response) {
    return (
      <section className="hal-workstation-card" aria-labelledby="hal-recommendation-title">
        <p className="eyebrow">Recommendation / next step</p>
        <h2 id="hal-recommendation-title">HAL is ready for the next office question.</h2>
        <p>Ask HAL to review a patient, claim, missing documentation, payer status, or today&apos;s practice priorities.</p>
      </section>
    );
  }

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-recommendation-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">HAL&apos;s answer</p>
        <h2 id="hal-recommendation-title">Here&apos;s what I found</h2>
      </div>
      <div className="hal-answer-card__section hal-answer-card__section--lead">{response.answer}</div>
      {speechControls ? (
        <details className="hal-accessibility">
          <summary>Accessibility (read aloud)</summary>
          {speechControls}
        </details>
      ) : null}
    </section>
  );
}
