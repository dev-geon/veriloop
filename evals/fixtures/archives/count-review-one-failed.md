# Fixture review with one Failed finding

One of the two findings survived the repair; this review becomes the next baseline.

```json
{
  "verdict": "fail",
  "findings": [
    {
      "severity": "failed",
      "title": "The repair keeps ISO dates",
      "file": "a.py",
      "line": 1,
      "confidence": "confirmed",
      "fix_hint": "fixture",
      "repair_plan": {
        "invariant": "ISO dates are preserved",
        "root_cause": "fixture",
        "affected_paths": ["a.py"],
        "implementation_steps": ["fixture"],
        "verification_cases": ["fixture"],
        "non_goals": []
      }
    }
  ]
}
```
