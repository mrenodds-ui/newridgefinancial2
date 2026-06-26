import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { fetchHalPatientDossier } from "../../api/client";
import { MissingDataNotice } from "./MissingDataNotice";
import { OFFICE_MANAGER_SAFETY_LABELS, SafetyLabelStrip } from "./SafetyLabelStrip";

export function PatientPrepPanel({
  onPrefillDraftQuery,
}: {
  onPrefillDraftQuery?: (query: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const dossierMutation = useMutation({
    mutationFn: (nextQuestion: string) => fetchHalPatientDossier(nextQuestion),
  });

  const canAsk = question.trim().length >= 3 && !dossierMutation.isPending;
  const dossier = dossierMutation.data;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-patient-prep-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Patient prep</p>
        <h2 id="hal-patient-prep-title">Patient / claim summary before a call or visit</h2>
        <p>
          HAL prepares bounded patient/claim context for staff review. Clinical context requires authorization; A/R
          appears only when a real source exists.
        </p>
      </div>
      <SafetyLabelStrip labels={[...OFFICE_MANAGER_SAFETY_LABELS]} />
      <div className="hal-draft-form">
        <label>
          Patient / claim question
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Prepare John Doe crown claim call"
          />
        </label>
        <button
          type="button"
          className="refresh-button"
          disabled={!canAsk}
          onClick={() => dossierMutation.mutate(question.trim())}
        >
          {dossierMutation.isPending ? "Loading patient prep..." : "Load patient prep summary"}
        </button>
        {onPrefillDraftQuery ? (
          <button
            type="button"
            className="refresh-button"
            disabled={question.trim().length < 3}
            onClick={() => onPrefillDraftQuery(question.trim())}
          >
            Use in draft for review
          </button>
        ) : null}
      </div>
      {dossierMutation.isError ? (
        <p className="hal-inline-error" role="alert">
          {dossierMutation.error instanceof Error
            ? dossierMutation.error.message
            : "Patient prep summary could not be loaded. Check SoftDent roles."}
        </p>
      ) : null}
      {dossier ? (
        <article className="hal-artifact-card">
          <h3>{dossier.matched ? "Patient prep summary" : "No patient match"}</h3>
          <p>{dossier.summary}</p>
          {dossier.supporting_context.length ? (
            <>
              <h4>Bounded supporting context</h4>
              <ul>
                {dossier.supporting_context.map((item) => (
                  <li key={item.source_id}>
                    <strong>{item.title}</strong>: {item.excerpt}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {!dossier.matched ? (
            <MissingDataNotice
              title="Patient context not matched"
              detail="HAL will not fabricate patient facts. Refine the patient or claim question."
            />
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
