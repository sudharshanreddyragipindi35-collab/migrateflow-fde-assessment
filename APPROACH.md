# MigrateFlow: approach and autonomy

## Approach

I built MigrateFlow around the implementation consultant's task: turn inconsistent employee exports into a trustworthy migration without approving every field. Multiple CSV/Excel files are profiled against one target schema, mapped, cleaned, reconciled and validated before delivery to a mock API. The React interface exposes progress, exceptions, source provenance and per-record outcomes. My central design decision is that the model proposes meaning; deterministic code controls execution.

## What the agent handles independently

Verified aliases with compatible types bypass inference. Unfamiliar columns receive structured proposals from the open-source Qwen2.5 model through Ollama, using masked profiling context. A mapping is applied automatically only when its evidence score is at least 0.90, types are compatible and no blocking ambiguity or collision exists. This score is a policy threshold, not a calibrated probability. The agent safely trims whitespace, normalizes known casing, converts unambiguous dates and merges clear duplicates. Batched inference and saved proposals reduce repeated work.

## Where I draw the escalation boundary

I escalate decisions that require missing business knowledge: competing field meanings, ambiguous dates, conflicting employee identities, missing required values or validation failures that safe cleanup cannot resolve. For example, `03/04/2024` must not be interpreted without evidence of the date convention. Model recovery or failover also triggers review. Confidence cannot override a collision or validation rule, and approval cannot make an invalid record valid. This boundary avoids both silent data corruption and unnecessary confirmation of routine transformations.

The review queue shows the relevant context, recommendation and reason, with approve, correct or reject actions. Human decisions persist, and resolving the final exception resumes processing. Selecting Autopilot authorizes delivery of valid records; guided mode keeps a separate send decision.

## Reliability beyond model output

A persistent SQL workflow and background queue keep execution independent of the browser. The mock API provides per-record results, idempotent delivery, bounded retries and batch-scoped undo. Audit records explain changes and decisions. Regression coverage checks ambiguity, collisions, preserved human corrections, unattended execution and retry/undo behavior. These controls make the agent's actions inspectable and recoverable; the small evaluation suite is not a claim of production accuracy.

## What I would build next

With a real client, I would first expand evaluation using representative exports and measure incorrect automatic decisions, review workload and completion time. Next I would add destination-specific authentication and rate limits, tenant isolation, encrypted storage and stronger distributed recovery. The priority is increasing safe autonomy with evidence while keeping the consultant's workflow understandable.
