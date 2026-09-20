# Submission review â€” 20 September 2026

## Verdict

Historical review before remediation. The five reproduced findings below are now covered by regression tests and repaired. See CURRENT_VALIDATION.md for the revised implementation and remaining demo-verification work.

Not ready for an unconditional submission sign-off. The core prototype and FDE concepts are present, and all existing local quality gates pass. Five focused regression probes nevertheless reproduced correctness problems. Fix these, reconcile the autonomy claim with the brief, and complete the required demo evidence before submitting.

Scope: compared the complete one-page Darwinbox assignment PDF with current working-tree code, documentation, and tests. Existing uncommitted work was included. This review did not change application code, commit files, publish anything, or rerun the historical Docker, load, or live-model checks.

## Reproduced findings

1. **High: rejecting a record with multiple errors leaves the workflow stuck.** In `backend/app/agent/service.py:183`, the remaining-escalation query runs before sibling resolutions are flushed. `SessionLocal` disables autoflush in `backend/app/db/database.py:27`. Rejecting a record with two validation errors returned `PAUSED`, with one reported open escalation; a subsequent escalation query returned zero open items. Flush changes before counting, and test that rejection resumes the pipeline.

2. **High: impossible dates crash cleanup instead of escalating.** `backend/app/cleaning/service.py:35` calls `datetime.strptime` without handling invalid calendar dates. A `hire_date` value of `2024-02-30` raised `ValueError: day is out of range for month`. Preserve the source value and produce an actionable validation escalation; do not fail the whole migration.

3. **High: the direct target route bypasses the batch review gate.** For the same batch with unresolved record review, `/mock-target/migrations/{id}/push-valid` returned 409, but `/mock-target/employees` returned 200/SUCCESS for a valid staged row. `backend/app/integration/service.py:38` verifies staged validity but not workflow approval. If the direct route is intentionally a target-only stub, put the caller's authorization gate at the connector boundary and explain that separation; otherwise enforce the batch/push decision consistently across every public write path.

4. **High: mapping collision review allows silent overwriting.** Approving both `email` and `work_email` mapped to `email` was accepted. Transformation returned only `second@example.com`; the first value was overwritten. `backend/app/agent/service.py:239` accepts a target already assigned to another source column, and `backend/app/cleaning/service.py:48` writes into a dictionary without resolving that conflict. Require choosing one source, rejecting the other, or an explicit merge/precedence policy.

5. **Medium: target failures still mark the pipeline completed.** A demo retryable target failure produced target status `RETRYABLE_FAILURE` while the pipeline returned `COMPLETED`. `backend/app/api/pipeline.py` counts successful writes but unconditionally completes the push stage and pipeline. Represent partial/complete failure explicitly and reconcile pipeline status after retry or rollback.

The focused reproducer is `tmp/submission_review_probe.py`. It uses a separate temporary database and synthetic records. These cases are not covered by the current passing suite.

## Assignment coverage

| Requirement | Assessment |
|---|---|
| Multiple CSV/Excel files, automatic reconciliation | Implemented; existing multi-file end-to-end test passes. Collision/identity edge cases need stronger regression coverage. |
| Autonomous mapping and safe cleanup | Implemented with structured model proposals, deterministic evidence and policy. Fix date and collision findings. |
| Escalate only genuine uncertainty | Meaningful boundary exists: 0.90 score, type compatibility, collision and ambiguity checks. Fix the stuck rejection path. |
| Live supervisor UI, approve/correct/reject | Implemented; frontend tests pass. No fresh browser walkthrough was performed in this review. |
| Mock API, per-record results, retry/rollback/audit | Implemented as an in-process stub with public API routes. Correct approval enforcement and failed-push status. The pipeline directly calls `push_valid`; it does not make an outbound HTTP request to an independent target. Clarify this prototype boundary. |
| Delta solutioning beyond AI output | Strong coverage: deterministic policy, validation, PII minimization, provenance, idempotency, compensation and audit. |
| Open-source AI model | Ollama adapter and configuration exist. Recorded submission should demonstrate actual Ollama proposals; deterministic fallback or Anthropic alone does not demonstrate this constraint. Historical live-model claims were not reverified here. |

The brief asks for autonomous pushing with human intervention for uncertainty. Autopilot currently always stops at `AWAITING_PUSH_DECISION`. This is a defensible customer policy, but a stricter reading of the brief sees an extra mandatory approval. State the deviation explicitly, or implement a clearly pre-authorized autonomous mock-push mode that still blocks on unresolved ambiguity.

## Is this a proper agent?

Yes, as a bounded AI-assisted migration workflow: it observes source profiles, proposes semantic mappings, evaluates confidence, applies safe actions, persists state, pauses for a person, resumes and records outcomes. Deterministic authority is appropriate for employee migration.

It is not five independent reasoning agents. Upload/Analyze/Review/Validation/Integration are specialized workflow stages with UI labels; the model's actual role is semantic mapping. `backend/app/agent/graph.py` supplies a tested LangGraph interrupt contract, but the application runtime uses SQL-backed orchestration in `agent/service.py` and `api/pipeline.py`. Do not pitch this as a deployed LangGraph multi-agent system.

RAG, vector databases, MCP, autonomous delegation and extra agents are not requirements of this assignment. Adding them would not repair the observed gaps.

## System design and FDE assessment

Good prototype foundations: HLD and LLD, schema contracts, separation of model advice from execution, provider abstraction, explicit uncertainty, resumable persisted state, customer-facing correction flows, audit, idempotency, retry classification, compensation, Docker configuration, PostgreSQL pooling and a documented capacity roadmap.

Production boundaries remain material: no authentication/RBAC/tenant isolation, durable background scheduler, distributed stage locking, or full production telemetry. These are not mandatory take-home requirements, but should be described as future work.

In particular, persisted stage state is not automatic crash recovery. Processing occurs inside HTTP requests, and `LiveRun.tsx:61` automatically advances only an ACTIVE/QUEUED stage. A process crash after committing RUNNING can leave no automatic recovery path. Concurrent advance requests also lack a database claim/lease. Avoid presenting the current implementation as a durable distributed worker system.

## Evidence integrity and deliverables

- `scripts/evaluate.py:17` hard-codes validation pass rate, duplicate reconciliation accuracy and push success after retry to 1.0. Its auto-apply precision divides by expected auto-applications, and escalation precision uses expected escalations, rather than the respective predicted counts. Recalculate true metrics from actual outcomes and add failing cases. The current six-case deterministic evaluation does not establish live-model quality.
- `FINAL_VALIDATION.md` still reports 42 backend tests and 7 frontend tests and says GO. This review ran 47 and 10, respectively, and found additional failures. Update the verdict and distinguish fresh checks from historical results.
- `APPROACH.md` includes approach, autonomy boundary and next steps. Check its rendered length to honor the one-page maximum; Markdown alone does not establish page count.
- Local run instructions exist. The short demo recording is still unchecked in `SUBMISSION_CHECKLIST.md`; no tracked video was found. For the local-instructions submission route, the brief requires the recording, including an escalation resolved in the UI. A demo script is not the recording. A separately hosted recording may exist outside this workspace; it was not verified.
- README screenshots are useful polish, not an explicit assignment requirement.
- Several current implementation files are untracked, including the pipeline modules and `SupervisedRun.tsx`. Ensure the final repository submission includes these after fixes and verification. Do not include secrets, runtime databases or uploads.

## Fresh checks

| Check | Result |
|---|---|
| Backend pytest | 47 passed; deprecation warnings only |
| Backend Ruff | Passed |
| Backend mypy | Passed, 45 source files |
| Frontend Vitest | 10 passed across 3 files |
| Frontend ESLint | Passed |
| Frontend TypeScript and Vite production build | Passed |
| Focused review probes | Reproduced all five findings above |
| Docker, live Ollama, production replicas/load, browser walkthrough | Not rerun in this review |

Recommended completion order: repair the five reproduced issues and add regressions; fix evaluation calculations and documentation claims; settle and document the autonomous-push boundary; run a fresh Ollama walkthrough; record the required UI escalation; verify the final repository contents.

