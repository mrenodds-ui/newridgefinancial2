# Judge Rubric

Score each category from 1 to 5.

- Grounding: The answer is supported by the supplied reference facts and does not introduce unsupported claims.
- Coverage: The answer covers the key required facts without omitting essential boundaries.
- Format: The answer obeys the requested structure and stays concise.
- Tone: The answer is direct, operational, and non-fluffy.

Return JSON only in this shape:

```json
{
  "scores": {
    "grounding": 5,
    "coverage": 5,
    "format": 5,
    "tone": 5
  },
  "average_score": 5.0,
  "pass": true,
  "rationale": "Short explanation."
}
```