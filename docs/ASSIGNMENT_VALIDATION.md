> Updated implementation: see `docs/REQUIREMENTS_AND_VERIFICATION.md` (or `REQUIREMENTS_AND_VERIFICATION.md` from docs) and `docs/CURRENT_VALIDATION.md`. Counts and runtime claims below are historical; they are not a fresh sign-off for the revised implementation.

# Darwinbox Assignment Validation

This matrix treats the take-home brief as the product requirements source and maps each acceptance criterion to running code, tests, and demo evidence.

| Brief criterion | Status | Implementation evidence | Demo evidence |
|---|---|---|---|
| Multi-file ingestion and reconciliation | PASS | One batch accepts multiple CSV/XLSX files. `records.py` transforms all sources, merges exact cross-file identities, retains source provenance, and routes conflicting identities to review. | Upload the three files in `sample_data/`; show `IN001` represented once with both source filenames. |
| Autonomous mapping and cleanup | PASS | Structured model proposals are combined with deterministic alias, type, pattern, uniqueness, and collision evidence. Scores at or above 0.90 auto-apply when safe. Cleanup handles whitespace, Unicode, casing, email, phone, and unambiguous dates. | Show obvious aliases auto-applied and deterministic provenance in Data Preview. |
| Defensible escalation boundary | PASS | Low-confidence mappings, collisions, ambiguous dates, identity conflicts, and fields still invalid after two attempts pause. Exact duplicates and high-confidence mappings do not pause. Thresholds and reasons are recorded. | Explain one auto-applied mapping, one ambiguous mapping, and one field-level record correction. |
| Human-in-the-loop UI | PASS | Live SSE activity, actionable review cards, confidence/reason context, and allowed Approve/Correct/Reject controls are implemented. Record corrections are revalidated before resume. | Resolve at least one mapping and one record value in Review Queue. |
| Mock system integration | PASS | Valid records are pushed with idempotency keys and payload hashes. Per-record results, bounded retry, batch-scoped rollback, events, and audit records are implemented. Push is blocked while reviews remain open. | Enable `DEMO_FAILURES`, show retryable failure, retry success, and rollback. |
| Delta solutioning beyond model output | PASS | The model is advisory. Deterministic policy, PII minimization, schema validation, reconciliation, provenance, idempotency, retry classification, rollback, observability, and capacity design are code-owned safeguards. | Contrast the model proposal with the policy decision and deterministic evidence. |

## Deliverables

| Deliverable | Status | Location or action |
|---|---|---|
| Working prototype | PASS | Docker local run instructions in `README.md`; backend and frontend health checks pass. |
| Source repository and setup/stack README | PASS | Repository `migrateflow`; setup, model configuration, architecture, testing, and troubleshooting are documented. |
| One-page approach | PASS | `APPROACH.md` focuses on the autonomy/escalation boundary and next steps. |
| Short demo recording | MANUAL | Record the sequence in `DEMO_SCRIPT.md`; include at least one resolved escalation. |

## Submission model choice

Run the recorded assignment demo with `MODEL_MODE=ollama` and `OLLAMA_MODEL=qwen2.5:7b-instruct` to satisfy the open-source-model constraint. Anthropic remains an optional adapter that demonstrates provider abstraction, but it should not be the provider shown as the primary assignment path.

## Honest prototype boundaries

The local prototype is intentionally compact. SQLite and bounded background processing are suitable for the take-home demonstration, while the checked-in production design moves to PostgreSQL, durable jobs, object storage, shared event fanout, rate limiting, and stateless replicas. The 2,000- and 10,000-user tiers are capacity plans, not claims of completed production certification.
