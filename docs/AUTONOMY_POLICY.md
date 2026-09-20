# MigrateFlow Autonomy Policy

## Authority boundary

The model proposes semantic mappings and explanations. It cannot decide whether its proposal executes. Code evaluates inspectable evidence, collisions, validation state, and policy warnings before any automatic action.

## Execution modes

Autopilot automatically advances reversible, policy-approved agent stages and pauses on genuine ambiguity. Human-in-the-loop keeps the original supervised flow where the consultant starts analysis, resolves uncertainty, inspects preview data, and initiates the push. Neither mode can silently bypass an escalation, and both require authorization: Autopilot receives permission to send to the mock destination when the migration starts; guided mode waits for an explicit send decision.

## Automatic actions

Only reversible, deterministic cleanup and high-confidence, unambiguous mappings may proceed automatically. Automatic decisions must meet configured thresholds and create audit evidence.

## Human decisions

Collisions, disputed required fields, ambiguous dates, conflicting identity evidence, and low-confidence mappings pause the workflow. A reviewer may approve, correct, or reject the proposal. The system resumes the same durable workflow thread and records the actor and decision.

## External effects

Every external write requires an idempotency key and payload hash. Retries are bounded and apply only to retryable failures. Rollback compensates only records created by the selected batch.

## Failure behavior

Invalid model output, unavailable dependencies, validation failures, and integration errors remain explicit states. Mock operation is labelled, configured separately, and never claims model intelligence.
