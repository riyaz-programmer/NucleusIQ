# Challenge 01 — Scorecard Specification

Every submission must produce a `result.json` file with the fields below. This is the **only** way submissions are compared.

If a field cannot be reported by your framework, use `null` and explain in `notes`. The whole point of the challenge is to see what each framework can or cannot expose.

## Required Fields

```json
{
  "framework": "string — e.g. nucleusiq, langchain, crewai, plain_openai, custom",
  "framework_version": "string",
  "model": "string — e.g. gpt-4.1-mini",
  "provider": "string — e.g. openai, anthropic, groq",
  "task_completed": "bool — true if the agent produced all four task sections",
  "duration_seconds": "number",
  "tool_calls": "int",
  "llm_calls": "int",
  "estimated_input_tokens": "int — null if not exposed",
  "estimated_output_tokens": "int — null if not exposed",
  "estimated_cost_usd": "number — null if not exposed",
  "peak_context_utilization": "number 0.0-1.0 — null if not exposed",
  "compaction_events": "int — null if framework has no notion of compaction",
  "tokens_freed_total": "int — null if not exposed",
  "final_answer_has_recommendation": "bool",
  "final_answer_has_top5_risks": "bool",
  "final_answer_has_evidence_per_risk": "bool",
  "final_answer_has_unknowns": "bool",
  "files_cited_in_evidence": "int — how many of the 5 data files were cited by name",
  "boilerplate_quoted_as_evidence": "bool — true if marketing copy or dashboard headers were quoted",
  "final_answer": "string — full agent output, truncate to 4000 chars if larger",
  "notes": "string — anything about failures, retries, setup issues, missing fields"
}
```

## How To Score (informal)

There is **no single winner**. The point of publishing the scorecard is to compare frameworks across multiple dimensions.

Compare on:

1. **Did it complete?** — `task_completed`, did it cite ≥4 of 5 files.
2. **How efficient?** — `duration_seconds`, `tool_calls`, `llm_calls`, `estimated_cost_usd`.
3. **How observable?** — how many fields the framework can populate vs. report as `null`.
4. **How honest?** — did it quote marketing boilerplate as evidence.
5. **Did context become a problem?** — `peak_context_utilization`, `compaction_events`, `tokens_freed_total`.

## Where To Submit

The default submission path is the **pinned GitHub Discussion** linked at the top of `README.md`. Reply with your `result.json` in a fenced JSON code block plus 2–3 lines about your stack.

Pull requests adding to `submissions/<your_handle>_<framework>/` are welcome **by invitation** after a maintainer has seen your Discussion entry. This keeps the folder curated. Direct PRs without prior Discussion may be closed with a request to post in the Discussion first.

See the "How To Submit" section of `README.md` for the full rules.
