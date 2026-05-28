# Challenge 01 — The Task

This file is the **canonical task definition**. Every submission must solve exactly this task. Do not edit it once the challenge is published.

## Scenario

You are a careful investment-risk analyst. Aurora Retail Systems is a fictional Series-B SaaS company. Five noisy internal documents are provided in the `data/` folder. They contain useful facts, repeated boilerplate, conflicting signals from the CEO vs. finance, marketing copy, and dashboard exports.

## What The Agent Must Do

1. Inspect **every file** in `data/`.
2. Treat **repeated boilerplate** (dashboard headers, marketing blurbs, service-desk macros, vendor profile metadata, appendix noise) as a **single piece of context**, not as independent evidence.
3. Produce a single response containing all four sections below:

```
Final Recommendation: <one paragraph>

Top 5 Risks:
  1. <risk title> — <severity>
     Evidence:
       - <quoted or paraphrased finding> (<source file>)
       - ...
  2. ...

Unknowns / Diligence Questions:
  - <question>
  - ...
```

## What Counts As A Correct Answer

A submission is **correct enough** if:

- It produces all four sections (recommendation, top 5 risks, evidence per risk, unknowns).
- At least four of the five data files are cited by name in the evidence.
- It does not repeat the same boilerplate paragraph as multiple distinct pieces of evidence.

## What The Agent Must NOT Do

- Refuse the task.
- Crash because of context overflow.
- Hallucinate file names that are not in `data/`.
- Quote marketing copy as analyst evidence.

## Why This Task

This task was chosen because it is intentionally hostile to "throw everything in one prompt" agents. It forces the framework to:

- Use tools (the data files are too long to paste into the system prompt comfortably).
- Manage context (the noise will accumulate as the agent reads more files).
- Surface evidence (the deliverable is structured, not freeform chat).
- Be observable (the scorecard requires real telemetry).

If a framework cannot pass this task with a small model on a tight budget, it will not survive a real production agent workload.
