> Updated implementation: see `docs/REQUIREMENTS_AND_VERIFICATION.md` (or `REQUIREMENTS_AND_VERIFICATION.md` from docs) and `docs/CURRENT_VALIDATION.md`. Counts and runtime claims below are historical; they are not a fresh sign-off for the revised implementation.

# MigrateFlow Final Validation

## Status

Historical validation record. Final submission still requires the short demo recording for the local-run route and fresh live-model/UI verification. Consult CURRENT_VALIDATION.md for the current checks.

## Environment

- Host: Windows
- Container runtime: Docker 29.6.2
- Runtime contract: Python 3.12 container, Node.js 22 container
- Local verification: Python 3.13.3, Node.js 24.11.1
- Persistence: SQLite local profile; PostgreSQL production configuration and pooling added
- Model paths: Ollama `qwen2.5:7b-instruct`, optional Anthropic `claude-sonnet-4-6`, and explicit deterministic fallback

## Commands and results

| Gate | Command | Result |
|---|---|---|
| Backend lint | `python -m ruff check app tests` | PASS |
| Backend types | `python -m mypy app` | PASS, 43 source files |
| Backend tests | `python -m pytest -q` | PASS, 42 tests, including production-path multi-file reconciliation, adaptive model-response recovery, supervised outage fallback, plain-language validation guidance, record correction, and safe model-runtime reporting |
| Frontend lint | `npm run lint` | PASS |
| Frontend tests | `npm test` | PASS, 7 tests |
| Frontend build | `npm run build` | PASS |
| Evaluation | `python scripts/evaluate.py` | PASS, 6 cases and 8 metrics |
| Container build | `docker compose up -d --build` | PASS |
| Production profile | `docker compose -f docker-compose.production.yml up -d --build --scale backend=2` | PASS, 2 healthy API replicas behind Nginx and PostgreSQL |
| Load smoke | `python scripts/load_test.py --base-url http://localhost:8080 --users 200 --requests-per-user 5 --max-p95-ms 1500` | PASS, 1,000 requests, 0 errors, p95 525.08 ms on this workstation |
| Backend health | `GET http://localhost:8000/health` | PASS, `status=ok` |
| Frontend health | `GET http://localhost:5173` | PASS, HTTP 200 |
| Anthropic mapping smoke | `POST /api/batches/{id}/mapping-proposals` | PASS, 4 proposals from `anthropic`; all 4 routed to human review |
| Ollama structured mapping smoke | `OllamaMappingAdapter.propose(...)` | PASS, `qwen2.5:7b-instruct` returned a schema-valid `email` mapping |
| Docker-to-Ollama connectivity | `GET host.docker.internal:11434/api/tags` from backend container | PASS, configured model visible |
| Transactional smoke | `python scripts/smoke_test.py` | PASS, upload through push and compensating rollback |
| Live Ollama smoke | `python scripts/smoke_test.py --live-model --timeout 300` | PASS, 7 structured proposals, 1 valid record, push and rollback |
| Batched Ollama mapping | One structured request for a 7-column source file | PASS, all 7 mappings correct in 126.06 seconds versus roughly 4.5 minutes for sequential calls |
| Abrupt spike | `python scripts/load_test.py --pattern spike --baseline-users 10 --users 200 --requests-per-user 5` | PASS, 1,000 spike requests, 0 errors, p95 616.54 ms |

## Requirement evidence

- Multi-file CSV/XLSX profiling and masked samples: `backend/app/ingestion/` and `backend/tests/test_ingestion.py`
- Cross-file exact-duplicate merge, conflict preservation, and source provenance: `backend/app/api/records.py`, `backend/app/cleaning/service.py`, and `backend/tests/test_end_to_end.py`
- Structured mapping and inspectable scoring: `backend/app/mapping/` and `backend/tests/test_mapping.py`
- Durable supervised pause and resume: `backend/app/agent/` and `backend/tests/test_workflow.py`
- Mapping and record-level review with approve/correct/reject boundaries: `backend/app/agent/service.py` and `frontend/src/pages/ReviewQueue.tsx`
- Plain-language correction guidance, date-format examples, and safe reject behavior: `backend/app/validation/employee.py`, `frontend/src/pages/ReviewQueue.tsx`, and their focused tests
- Deterministic cleaning, validation, and reconciliation: `backend/app/cleaning/`, `backend/app/validation/`, and `backend/tests/test_cleaning.py`
- Idempotent push, retry, and batch rollback: `backend/app/integration/` and `backend/tests/test_integration.py`
- Complete supervised scenario: `backend/tests/test_end_to_end.py`
- PII and prompt-injection controls: `backend/app/security.py` and `backend/tests/test_security.py`
- Consultant interface: `frontend/src/pages/`
- Provider abstraction and fail-closed Anthropic configuration: `backend/app/mapping/engine.py` and `backend/tests/test_mapping.py`
- HLD, LLD, capacity tiers, and GenAI controls: `docs/HIGH_LEVEL_DESIGN.md`, `docs/LOW_LEVEL_DESIGN.md`, `docs/SCALABILITY_AND_CAPACITY.md`, and `docs/GENAI_ENGINEERING.md`
- Load-balancer and PostgreSQL scale demonstration: `docker-compose.production.yml` and `deploy/nginx/nginx.conf`

## Known limitations

- A production rollout still needs versioned Alembic revisions, a durable queue, object storage, shared SSE fanout, and managed infrastructure.
- A live Ollama structured-output smoke passed on this workstation; model quality still needs a larger representative offline benchmark before client use.
- The evaluation set is small and should grow before a client deployment.
- The mock target demonstrates write semantics but not client authentication, quotas, or production networking.
- The 2k and 10k tiers are documented hypotheses and have not been certified by production-scale load and failure testing.
