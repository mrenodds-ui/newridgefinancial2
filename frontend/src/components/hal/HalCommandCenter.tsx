import type { FormEvent } from "react";

type HalCommandCenterProps = {
  question: string;
  setQuestion: (value: string) => void;
  useSecondOpinion: boolean;
  setUseSecondOpinion: (value: boolean) => void;
  questionTooShort: boolean;
  canSubmitQuestion: boolean;
  isPending: boolean;
  onSubmit: (event: FormEvent) => void;
};

export function HalCommandCenter({
  question,
  setQuestion,
  useSecondOpinion,
  setUseSecondOpinion,
  questionTooShort,
  canSubmitQuestion,
  isPending,
  onSubmit,
}: HalCommandCenterProps) {
  return (
    <section className="hal-workstation-card hal-command-center" aria-labelledby="hal-command-center-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Ask HAL command center</p>
        <h2 id="hal-command-center-title">Internal dental-office assistant</h2>
        <p>
          Ask in plain language. HAL can use authorized office context, SoftDent facts, drafts, local packets,
          knowledge memory, and runtime checks while staying inside local review boundaries.
        </p>
      </div>
      <form className="hal-command-center__form" onSubmit={onSubmit}>
        <label htmlFor="hal-question">What do you want HAL to help with?</label>
        <textarea
          className="hal-command-center__textarea"
          id="hal-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={5}
          placeholder="e.g. Review John Doe's denied crown claim and prepare next steps for staff review."
          required
          minLength={3}
          aria-invalid={questionTooShort || undefined}
          aria-describedby={questionTooShort ? "hal-question-length-hint" : undefined}
        />
        {questionTooShort ? (
          <p id="hal-question-length-hint" className="hal-inline-error" role="alert">
            Ask at least 3 characters.
          </p>
        ) : null}
        <label className="hal-command-center__checkbox">
          <input
            type="checkbox"
            checked={useSecondOpinion}
            onChange={(event) => setUseSecondOpinion(event.target.checked)}
          />
          Use deeper second opinion when needed
        </label>
        <button type="submit" className="refresh-button" disabled={!canSubmitQuestion}>
          {isPending ? "Asking HAL..." : "Ask HAL"}
        </button>
      </form>
    </section>
  );
}
