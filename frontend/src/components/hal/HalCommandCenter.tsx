import type { FormEvent, KeyboardEvent } from "react";

type HalCommandCenterProps = {
  question: string;
  setQuestion: (value: string) => void;
  questionTooShort: boolean;
  canSubmitQuestion: boolean;
  isPending: boolean;
  onSubmit: (event: FormEvent) => void;
  suggestions?: string[];
};

export function HalCommandCenter({
  question,
  setQuestion,
  questionTooShort,
  canSubmitQuestion,
  isPending,
  onSubmit,
  suggestions = [],
}: HalCommandCenterProps) {
  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      const target = event.currentTarget;
      const start = target.selectionStart ?? question.length;
      const end = target.selectionEnd ?? question.length;
      setQuestion(`${question.slice(0, start)}\n${question.slice(end)}`);
      return;
    }
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    if (!canSubmitQuestion || isPending) {
      return;
    }
    onSubmit(event);
  }

  return (
    <section className="hal-workstation-card hal-command-center" aria-labelledby="hal-command-center-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Ask HAL</p>
        <h2 id="hal-command-center-title">What do you need help with?</h2>
        <p>Ask in plain language. HAL can pull approved office data, summarize the work, and prepare review-ready next steps.</p>
      </div>
      {suggestions.length ? (
        <div className="hal-prompt-chips" aria-label="Suggested HAL prompts">
          {suggestions.map((suggestion) => (
            <button key={suggestion} type="button" onClick={() => setQuestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}
      <form className="hal-command-center__form" onSubmit={onSubmit}>
        <label htmlFor="hal-question">What do you want HAL to help with?</label>
        <textarea
          className="hal-command-center__textarea"
          id="hal-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleQuestionKeyDown}
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
        <button type="submit" className="refresh-button" disabled={!canSubmitQuestion}>
          {isPending ? "Thinking..." : "Ask HAL"}
        </button>
      </form>
    </section>
  );
}
