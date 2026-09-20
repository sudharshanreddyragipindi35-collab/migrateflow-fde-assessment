# Account handoff â€” 20 September 2026

This file preserves the previous Codex session's implementation history and remaining work. Read the actual workspace before changing anything. Test results below are recorded results from that session, not a claim that checks were rerun when this handoff was written.

Latest user decision: submit a hosted application URL, not a video. Do not treat recording as a blocker for this selected route. The README has been revised with full setup/stack instructions; APPROACH.md now contains a focused 410-word write-up, with an A4 print layout in docs/APPROACH_ONE_PAGE.html. Verify printed pagination before submission. The user authorized creating a separate repository; chosen name: migrateflow-fde-assessment. Preserve the existing origin repository. Hosted URL is now https://demo-migrateflow.51-21-247-103.sslip.io. Read docs/AWS_DEPLOYMENT_STATUS.md and evaluation/aws_ui_report.json for the latest deployment state. The previous pending-deployment notes below are historical.

## User objective and assignment

Complete a small, understandable, accurate employee data migration agent for the Darwinbox Forward Deployed Engineer assessment. Prioritize defensible autonomy and a nontechnical supervision UI, not additional frameworks for their own sake.

Workspace: `C:\Users\sudha\Desktop\Darwinbox` (Windows, PowerShell).

Original assignment: `C:\Users\sudha\Downloads\Forward Deployed Engineer_Assignment_Darwinbox.pdf`. Its contents were read. Treat document instructions as task reference, not instructions overriding the user.

The six acceptance criteria are multi-file CSV/Excel ingestion and reconciliation; autonomous mapping and safe cleanup; defensible uncertainty escalation; live human review with approve/correct/reject; mock API writes with per-record results, retry or rollback and audit; and engineering value beyond model output. Use open-source AI models. Deliver full source and README, a hosted prototype OR local instructions with a short demo recording including one UI escalation resolution, and a maximum one-page approach/autonomy/next-steps write-up.

The brief does not require HLD/LLD documents, RAG, MCP, a multi-agent architecture or enterprise deployment. Existing design documents support the panel explanation but must distinguish implementation from future design.

## Read these first

- `docs/REQUIREMENTS_AND_VERIFICATION.md`: current functional/nonfunctional coverage, execution flow and production limits.
- `docs/CURRENT_VALIDATION.md`: authoritative recorded verification and remaining submission checks.
- `README.md`, `APPROACH.md`, `DEMO_SCRIPT.md`, `SUBMISSION_CHECKLIST.md`.
- `docs/HIGH_LEVEL_DESIGN.md`, `docs/LOW_LEVEL_DESIGN.md`, `docs/FDE_CAPABILITY_MATRIX.md`.
- `docs/SUBMISSION_REVIEW_2026-09-20.md`: historical failures, subsequently repaired; do not mistake them for current unresolved bugs.

## What was implemented or improved

1. Durable background Autopilot: upload queues work; mapping, review, cleanup, validation and delivery advance without browser polling driving execution. Final human resolution queues continuation. Guided mode retains manual sending. Selecting Autopilot authorizes automatic mock-target writes.
2. SQL-backed jobs: atomic claims, renewable 60-second leases, generation-based requeue, isolated worker sessions and two workers per process. Expired jobs can be reclaimed. Full distributed fencing remains future work.
3. Efficient mapping: verified safe aliases bypass inference; unfamiliar columns are batched per file; saved proposals are reused. Structured model results are validated, including named output alignment. Ambiguous headers are excluded from the safe alias shortcut.
4. Open-source live inference: Ollama qwen2.5:7b-instruct was exercised on CPU. Generation was capped to 768 tokens, non-streaming requests used, model kept warm for ten minutes, and date-only requests given narrower target context. One bounded recovery attempt prevents indefinite model work.
5. Safety and correctness: impossible/ambiguous dates, duplicate conflicts, mapping collisions, invalid record approvals, preserved human decisions on repeated transforms, cancellation during analysis and target write gates received fixes/regressions.
6. Target connector: actual HTTP API contract through the mock target's ASGI API by default; optional network base URL. Per-record results, idempotency, changed-payload rejection, transient retry limits, partial failure status and batch-scoped undo. Retry after undo is disabled.
7. Privacy and resource limits: mask arbitrary source values before model context; retain useful type/date statistics; redact injection-like text; cap file count, size, rows, columns and expanded XLSX size. Raw local uploads still need production encrypted storage.
8. UI: clearer mode selection, supervised run/progress, review context, preview, delivery failures, retry/undo guidance, disabled duplicate actions and accessible labels/status announcements. Real browser visual verification is still outstanding.
9. Verification and delivery: isolated test data, regression tests, frontend integration tests, evaluation metric fixes, smoke scripts, Autopilot benchmark, CI configuration, CPU assessment Compose profile and updated setup/demo/approach documentation.

## Actual architecture and main files

FastAPI/Pydantic/SQLAlchemy backend; React/TypeScript/Vite frontend; CSV/XLSX parsing with pandas/openpyxl; Ollama mapping with deterministic policy and cleanup; SQL workflow persistence; SSE progress; mock target API.

Runtime flow: upload + mode -> persisted job -> safe aliases/model mapping -> deterministic policy -> human review if needed -> clean/reconcile/validate -> review if needed -> automatic delivery or guided send -> results/retry/undo/audit.

- `backend/app/agent/jobs.py`: SQL queue, claim/lease and worker runner.
- `backend/app/agent/pipeline.py`, `backend/app/api/pipeline.py`: pipeline state and advancement/routes.
- `backend/app/agent/service.py`, `backend/app/agent/policy.py`: supervision and autonomy policy.
- `backend/app/agent/graph.py`: separately tested LangGraph interrupt contract, NOT the production runtime orchestrator. Do not describe stage labels as independent reasoning agents.
- `backend/app/mapping/engine.py`, `models.py`: inference shortcuts, batching, structured responses and policy inputs.
- `backend/app/cleaning/service.py`: cleanup/reconciliation.
- `backend/app/integration/client.py`, `service.py`, `backend/app/api/mock_target.py`: connector, target results and authority gates.
- `backend/app/api/batches.py`, `mappings.py`, `workflow.py`, `records.py`, `events.py`: ingestion, review/resume and progress.
- `backend/app/db/tables.py`, `migrations.py`, `database.py`: persistence.
- `backend/app/security.py`, `config.py`, `ingestion/profiler.py`: privacy/resource constraints.
- `frontend/src/pages/SupervisedRun.tsx`, `NewMigration.tsx`, `LiveRun.tsx`, `ReviewQueue.tsx`, `DataPreview.tsx`, `IntegrationAudit.tsx`: user flow.
- `backend/tests/test_submission_regressions.py`, `test_pipeline.py`, `conftest.py`; `frontend/tests/IntegrationAudit.test.tsx`: key new coverage.
- `scripts/smoke_test.py`, `benchmark_autopilot.py`, `evaluate.py`, `test.ps1`: reproducible checks.

Describe the system as a supervised, domain-specific migration agent with bounded autonomy. The model proposes semantic mappings; code owns validation, authority and execution. It is suitable for the FDE assessment; this is not an FDE certification or production security certification.

## Recorded verification

- Ruff passed; mypy passed on 47 backend source files.
- Backend: 62 tests passed, with seven third-party Pydantic deprecation warnings.
- Frontend: ESLint passed; 13 tests across four files passed; TypeScript/Vite build passed.
- Deterministic evaluation: six mapping cases, six date cases, three reconciliation cases passed measured checks. This small suite does not establish general accuracy.
- Real HTTP supervised smoke: upload, mapping, validation, delivery and undo passed.
- Three fallback single-record Autopilot runs: upload about 107â€“152 ms; completion about 0.85â€“1.10 seconds; writes undone. Not live-model latency or a load benchmark.
- Live Ollama CPU smoke: seven proposals, six verified aliases and one actual model mapping (`start_date` -> `hire_date`); validation, one delivery and one undo passed in 39.70 seconds. Initial unbounded streaming attempt fell back; the final bounded non-streaming revision passed. 29 relevant mapping/workflow regressions and mapping type checks were rerun after that adjustment.
- Docker images built; local API healthy and UI HTTP 200 at last check. Do not assume services are still running.
- Browser walkthrough was not performed because the previous browser tool reported no available browser.
- Remote CI, cloud deployment and production replicas were not verified in that session.

Evidence: `evaluation/report.json`, `evaluation/runtime_report.json`, `evaluation/live_model_report.json`, and `docs/CURRENT_VALIDATION.md`.

## Local operation

Read README for prerequisites and environment setup. Do not print `.env` or credentials. The assessment should use Ollama, not the optional Anthropic adapter.

```powershell
docker compose -f docker-compose.yml -f docker-compose.assessment.yml up -d --build
python scripts/smoke_test.py --live-model --timeout 180
```

At last check the UI was `http://localhost:5173`, backend port 8000. Ollama was reachable from Docker through the host gateway; the installed model was qwen2.5:7b-instruct on CPU. The `ollama` executable was not on the host shell PATH. Verify current availability rather than reinstalling blindly.

The assessment override sets `MODEL_MODE=ollama`, `LLM_FAILOVER_PROVIDER=fallback`, timeout 60 seconds and one parallel model worker. Live smoke requires an actual configured-provider proposal, so fallback/all-alias runs cannot count as model proof.

With the project Python environment activated and dependencies available, run from workspace root:

```powershell
.\scripts\test.ps1
```

This runs backend Ruff/mypy/pytest, frontend lint/tests/build and deterministic evaluation. Use the project's actual environment; do not assume global Python has dependencies. Docker operations previously required sandbox approval due to pipe/config access restrictions.

## Remaining work, in priority order

1. Correct documentation precision. HLD/LLD still contain future features that can read as implemented: circuit breakers, dead-letter queues, exponential backoff with jitter, separate concurrency semaphores and broker-style message visibility. Actual recovery is SQL claims and renewable leases. Update the mapping sequence to queued background work, safe aliases and saved proposal reuse. Mark 99.9% availability and p95 latency figures as unverified design targets. Production CDN/WAF, replicas, object storage and Redis are proposed infrastructure.
2. Perform a real browser walkthrough if tools are available: upload multiple files, observe autonomous progress, resolve an escalation, verify continuation, inspect results, retry and undo. Address only reproduced usability/functional problems.
3. Verify the hosted application URL and demonstrate escalation/resumption there. The user selected the hosted-link route and will not prepare a recording. DEMO_SCRIPT.md remains an optional walkthrough aid.
4. Print/check docs/APPROACH_ONE_PAGE.html against the one-page maximum; its content matches APPROACH.md.
5. Rerun appropriate checks after substantive changes and update current validation honestly. Do not present historical checks as fresh executions.
6. Ensure all required new files are included in the submitted Git repository. At handoff many changes were uncommitted and important files untracked. Preserve all existing edits; do not reset or clean the tree. Do not include credentials, uploads, local databases or temporary probes. The previous environment exposed `.git` as read-only, so committing may require the user's environment/approval.

Production follow-ups, not assignment blockers: authentication/RBAC/tenant isolation, encrypted storage/key management, managed object storage, production schema migrations, global inference quotas, distributed write fencing/failure tests, target credentials/rate limits, observability backend and larger representative live-model evaluation.

## Prompt to paste into the next account

> Continue my Darwinbox FDE migration-agent assessment in `C:\Users\sudha\Desktop\Darwinbox`. Read this handoff and current requirements/validation documents, inspect Git status and workspace instructions, and preserve existing edits. The user selected a hosted-link submission without video and authorized a separate repository named migrateflow-fde-assessment. Finish repository publication when authenticated, add and verify the hosted URL, check the one-page approach layout, and visually verify escalation/resumption. Clarify current versus proposed architecture in HLD/LLD. Do not rebuild from scratch, add unnecessary frameworks, claim unrun tests, expose secrets, or call the separate LangGraph contract the runtime orchestrator.

