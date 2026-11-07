# Fixture review with two Failed findings

The same invariant fails in two files; the next review's count is compared with this one.

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
    },
    {
      "severity": "failed",
      "title": "The repair keeps ISO dates",
      "file": "b.py",
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
