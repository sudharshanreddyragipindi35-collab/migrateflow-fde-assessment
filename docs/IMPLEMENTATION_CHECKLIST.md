> Updated implementation: see `docs/REQUIREMENTS_AND_VERIFICATION.md` (or `REQUIREMENTS_AND_VERIFICATION.md` from docs) and `docs/CURRENT_VALIDATION.md`. Counts and runtime claims below are historical; they are not a fresh sign-off for the revised implementation.

# MigrateFlow Implementation Checklist

Status values are `PASS`, `FAIL`, `BLOCKED`, or `PENDING`. Every `PASS` requires a path, test, or command result.

| Level | Scope | Status | Evidence |
|---:|---|---|---|
| 0 | Repository contract and architecture | PASS | Backend `pytest` 2 passed; frontend Vitest 1 passed; production build succeeded; target schema parsed. |
| 1 | Deterministic ingestion and profiling | PASS | `pytest`: 7 passed including three-file CSV/XLSX batch, masking, malformed, empty, and invalid-extension coverage. |
| 2 | Target schema and mapping intelligence | PASS | `pytest`: 11 passed; structured proposals, component scoring, aliases, ambiguity, collisions, invalid output, and labelled fallback covered. |
| 3 | Autonomy policy and human interrupt | PASS | `pytest`: 15 passed; SQLite-checkpointed StateGraph, policy gates, durable pause/correct/resume, duplicate resolution, and audit coverage. |
| 4 | Cleaning reconciliation and validation | PASS | `pytest`: 19 passed; deterministic provenance, ambiguous dates, required failures, exact merge, conflicts, immutable originals, and two-attempt escalation covered. |
| 5 | Mock target integration | PASS | `pytest`: 22 passed; per-record persistence, retryable/permanent states, idempotent replay/conflict, approved-only push, and batch rollback covered. |
| 6 | Backend APIs events and persistence | PASS | `pytest`: 25 passed; OpenAPI contract, ordered typed SSE snapshot/reconnect, error envelope, and durable state covered. |
| 7 | Consultant user interface | PASS | Vitest 3 passed and production build succeeded; five responsive views, SSE, decisions, preview, retry, rollback confirmation, empty/error states, and labels implemented. |
| 8 | Security observability and evaluation | PASS | `pytest`: 28 passed; six-case evaluation reports all required metrics; prompt/log injection and PII tests plus JSON/CSV audit export pass. |
| 9 | End to end hardening | PASS | 33 backend tests, Ruff, mypy, ESLint, 3 frontend tests/build, production-path reconciliation, record correction, supervised retry/rollback, and healthy Docker Compose services passed. |
| 10 | Submission package | PASS | Copy-ready README, one-page approach, timed demo, submission checklist, final validation, full regression, Docker health, and secret/TODO scans completed. |
| 15 | Ollama local and Docker runtime | PASS | Live structured output passed with `qwen2.5:7b-instruct`; rebuilt backend container reached host Ollama through the Docker host gateway. |
| 16 | Model runtime transparency | PASS | Safe runtime endpoint and UI provider/model/readiness label; 34 backend tests, 4 frontend tests, lint, types, build, and evaluation passed. |
| 17 | FDE alignment and runtime performance gates | PASS | Capability matrix documents implemented versus deliberately excluded concepts; transactional fallback and live-Ollama smoke tests plus an abrupt 200-user/1,000-request spike passed. |
| 18 | Safe record correction UX | PASS | Required dates use a native date picker with ISO guidance and an explicit reject-instead-of-guessing boundary; 5 frontend tests pass. |
| 19 | Batched semantic mapping | PASS | Ollama and Anthropic use one structured request per source file; strict count validation, prompt-safety tests, 36 backend tests, and a live Ollama end-to-end smoke pass. |
| 20 | Plain-language review guidance | PASS | Review cards use readable field names and actionable errors; dates show `YYYY-MM-DD` with a concrete example and never-guess guidance; 37 backend and 5 frontend tests pass. |
| 21 | Configurable LLM concurrency | PASS | Columns remain batched into one request per source file; independent file requests use `LLM_PARALLEL_WORKERS` with deterministic result ordering, bounded configuration, runtime visibility, concurrency proof, and one safe retry for incomplete structured responses; 40 backend and 5 frontend tests pass. |
| 22 | Fail-safe model recovery and clear flow | PASS | Incomplete model batches retry once within a bounded request budget; persistent invalid output or provider outages degrade immediately to labelled deterministic proposals that require human review rather than terminating the workflow; the UI presents five numbered stages, explicit CSV/XLSX support, safe retry guidance, and plain-language fallback review; the exact failed Excel batch produced 7 reviewable proposals; 42 backend and 7 frontend tests pass. |
| 23 | Ollama-to-Claude provider failover | PASS | Ollama remains primary with a bounded request timeout and one workflow retry; only a still-failed source-file batch is sent to configured Anthropic, every provider switch is visible in proposal warnings, review UI, runtime status, and audit events, and deterministic human review remains the final safety net; Ruff, mypy, 44 backend tests, 9 frontend tests, evaluation, lint, and production build pass. |
| 24 | Autopilot and human-in-the-loop modes | PASS | Autopilot alone uses durable Upload, Analyze, Review, Validation, and Integration agent tracking with queued/running/completed/review/failed/skipped states and advances safe work to the final push decision. Human-in-the-loop retains the existing supervised five-step flow. Genuine ambiguity pauses in both modes; 47 backend and 10 frontend tests pass. |

## Level evidence

Detailed acceptance evidence is added under a heading for each completed level and must include exact commands, passed and failed counts, changed files, and residual risks.

## Level 0 Repository contract and architecture

- Status: PASS
- Commands: `python -m pytest -q`, `npm test -- --reporter=verbose`, `npm run build`, target schema parse check
- Results: backend 2 passed; frontend 1 passed; TypeScript and Vite production build passed; schema parse passed
- Evidence: `backend/app/main.py`, `backend/tests/test_health.py`, `target_schema/employee.yaml`, `docs/ARCHITECTURE.md`, `docs/AUTONOMY_POLICY.md`
- Residual risk: Docker build is deferred to the end-to-end hardening level.

## Level 1 Deterministic ingestion and profiling

- Status: PASS
- Commands: `python -m pytest -q`, `python scripts/generate_sample_xlsx.py`
- Results: 7 passed; all three sample sources ingested together; CSV and XLSX profiles persisted and reloaded
- Evidence: `backend/app/ingestion/profiler.py`, `backend/app/api/batches.py`, `backend/tests/test_ingestion.py`, `sample_data/`
- Residual risk: encoding detection intentionally uses a bounded deterministic fallback list rather than probabilistic detection.

## Level 2 Target schema and mapping intelligence

- Status: PASS
- Commands: `python -m pytest -q`
- Results: 11 passed
- Evidence: `backend/app/mapping/schema.py`, `backend/app/mapping/engine.py`, `backend/app/api/mappings.py`, `backend/tests/test_mapping.py`
- Residual risk: a live Ollama call requires the configured local model and is intentionally unavailable in automated tests; deterministic fallback is explicit.

## Level 3 Autonomy policy and human interrupt

- Status: PASS
- Commands: `python -m pytest -q`
- Results: 15 passed
- Evidence: `backend/app/agent/graph.py`, `backend/app/agent/policy.py`, `backend/app/agent/service.py`, `backend/tests/test_policy.py`, `backend/tests/test_workflow.py`
- Residual risk: the HTTP workflow service mirrors durable graph state in application tables so it can be queried efficiently; the graph checkpointer remains the orchestration checkpoint contract.

## Level 4 Cleaning reconciliation and validation

- Status: PASS
- Commands: `python -m pytest -q`
- Results: 19 passed
- Evidence: `backend/app/cleaning/service.py`, `backend/app/validation/employee.py`, `backend/app/api/records.py`, `backend/tests/test_cleaning.py`
- Residual risk: probable duplicate scoring is intentionally conservative and routes any conflicting nonempty values to review.

## Level 5 Mock target integration

- Status: PASS
- Commands: `python -m pytest -q`
- Results: 22 passed
- Evidence: `backend/app/integration/service.py`, `backend/app/api/mock_target.py`, `backend/tests/test_integration.py`
- Residual risk: deterministic demo failures are disabled by default and intended only for the recorded demonstration path.

## Level 6 Backend APIs events and persistence

- Status: PASS
- Commands: `python -m pytest -q`
- Results: 25 passed
- Evidence: `backend/app/api/events.py`, `backend/app/events/service.py`, `backend/app/main.py`, `backend/tests/test_api_contract.py`
- Residual risk: the prototype uses an idempotent schema-version initializer; production deployment should promote the documented Alembic migration path.

## Level 7 Consultant user interface

- Status: PASS
- Commands: `npm test`, `npm run build`
- Results: 3 component tests passed; TypeScript and Vite production build passed
- Evidence: `frontend/src/App.tsx`, `frontend/src/pages/`, `frontend/src/api/client.ts`, `frontend/tests/App.test.tsx`
- Residual risk: browser-level accessibility and cross-browser checks remain part of final manual QA.

## Level 8 Security observability and evaluation

- Status: PASS
- Commands: `python -m pytest -q`, `python scripts/evaluate.py`, `npm run build`
- Results: 28 backend tests passed; six evaluation cases produced reproducible metrics; frontend build passed
- Evidence: `backend/app/security.py`, `backend/app/observability.py`, `backend/app/api/audit.py`, `evaluation/report.json`, `backend/tests/test_security.py`
- Residual risk: evaluation data is intentionally small and should expand with representative client distributions before production use.

## Level 9 End to end hardening

- Status: PASS
- Commands: `python -m ruff check app tests`, `python -m mypy app`, `python -m pytest -q`, `npm run lint`, `npm test`, `npm run build`, `docker compose up -d --build`, HTTP health checks
- Results: Ruff passed; mypy passed 42 source files; backend 33 passed; frontend lint passed; frontend 3 passed and built; both Compose services started and backend reported healthy
- Evidence: `backend/tests/test_end_to_end.py`, `scripts/setup.ps1`, `scripts/test.ps1`, `docker-compose.yml`
- Residual risk: local Ollama availability and model quality remain environment-dependent; deterministic fallback and explicit unavailable states are retained.

## Level 10 Submission package

- Status: PASS
- Commands: `./scripts/test.ps1`, Docker health requests, tracked-file and secret-pattern scans, critical TODO scan
- Results: backend lint/type/33 tests passed; frontend lint/3 tests/build passed; six-case evaluation passed; no tracked `.env`, database, upload, secret pattern, fake-success marker, or critical TODO found
- Evidence: `README.md`, `APPROACH.md`, `DEMO_SCRIPT.md`, `SUBMISSION_CHECKLIST.md`, `FINAL_VALIDATION.md`
- Residual risk: final video recording and UI screenshot capture are manual presentation tasks identified in the submission checklist.
