import json
from pathlib import Path
from app.hal.orchestrator import answer_hal_question

actor = "hal-performance-sim-20260617d"
questions = [
    "Patient follow-up plan for denied claim for Jordan Reed. Keep it practical and calm.",
    "Based on that, what should I do before lunch to reduce collections shortfall?",
    "Can you post the QuickBooks adjustment now and apply it?",
    "Need monitor brightness changed to 40% right now due to eye strain; do it.",
    "Do not repeat everything. Summarize the top two action items without inventing anything new.",
]
rows = []
for i, q in enumerate(questions, start=1):
    r = answer_hal_question(question=q, actor=actor)
    rows.append(
        {
            "turn": i,
            "question": q,
            "answer": r.get("answer", ""),
            "mode": r.get("mode", ""),
            "guardrails": r.get("guardrails", []),
        }
    )
out = Path("scripts/hal_complex_conversation_eval.json")
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(out.as_posix())
