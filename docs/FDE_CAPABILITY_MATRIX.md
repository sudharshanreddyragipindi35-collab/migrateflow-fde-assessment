# FDE Capability Matrix

This matrix maps general Forward Deployed Engineer skills to the Darwinbox task. It distinguishes implemented, demonstrated capabilities from production follow-ups and concepts that are intentionally out of scope. The goal is a defensible customer solution, not a collection of unrelated AI patterns.

| FDE area | Status | MigrateFlow evidence or decision |
|---|---|---|
| Ambiguous-problem scoping | Implemented | `APPROACH.md` converts the brief into an autonomy boundary, trade-offs, and next steps. `ASSIGNMENT_VALIDATION.md` maps every acceptance criterion to code and demo evidence. |
| Python and API engineering | Implemented | FastAPI, Pydantic contracts, SQLAlchemy persistence, structured errors, SSE, idempotency, retries, and rollback. |
| Customer-facing frontend | Implemented | React consultant workflow for upload, live progress, review, correction, preview, integration results, and audit. |
| Open-source LLM integration | Implemented and live-tested | Ollama `qwen2.5:7b-instruct` produces schema-constrained mapping proposals. The UI exposes provider/model readiness. |
| Structured outputs and guardrails | Implemented | Pydantic model output, deterministic composite confidence, collision/type/date checks, masked context, prompt-injection filtering, and fail-closed errors. |
| Agent state and human approval | Implemented | Autopilot has durable SQL-backed specialized-agent tracking; Human-in-the-loop retains the established supervised workflow. In both modes high-confidence cases auto-apply, ambiguous cases pause with Approve/Correct/Reject, and Autopilot sends valid data under the permission established at upload while guided mode waits for a send action. A LangGraph contract tests the interrupt topology. |
| Long-running workflow design | Designed, compact runtime implemented | Checkpoints, resumable events, retries, and audit state are implemented locally. A SQL job queue with atomic claims and renewable leases runs two background workers per process. A managed broker and distributed fencing remain deployment follow-ups. |
| Evaluation | Implemented | Golden cases report mapping precision/recall, escalation precision/recall, reconciliation, validation, and retry outcomes. Deterministic and end-to-end regression tests protect behavior. |
| Runtime and performance verification | Implemented | Transactional deterministic and live-Ollama smoke tests, steady-load testing, abrupt spike testing, Docker health checks, and explicit thresholds. |
| Observability | Implemented for prototype | Correlation IDs, typed SSE events, audit exports, model provider labels, provenance, and safe error envelopes. Production metrics/tracing backend remains a deployment follow-up. |
| Security and privacy | Implemented for prototype | Upload limits, filename sanitization, PII masking, prompt-injection defense, no committed secrets, immutable originals, append-only audit protection, and batch isolation. |
| Authentication, RBAC, and tenant IAM | Production follow-up | Important for a real Darwinbox deployment, but not required by the brief and not falsely represented as complete. |
| Scalability and resiliency | Demonstrated and designed | Stateless API profile, Nginx load balancing, PostgreSQL pooling, bounded load/spike tools, idempotency, and capacity tiers. Queue, Redis fanout, object storage, autoscaling, and multi-zone failover are target architecture. |
| CI/CD and cloud rollout | CI configured; cloud not deployed | A GitHub Actions quality workflow, reproducible Docker builds and a fail-fast quality script exist; remote CI has not been run in this session. Managed cloud infrastructure and deployment pipelines require a selected customer cloud and IAM model. |
| RAG and vector retrieval | Not applicable | This task maps structured CSV/XLSX fields; retrieval would add cost and failure modes without addressing an acceptance criterion. |
| Multi-agent, deep-agent, and sub-agent delegation | Not applicable | Mapping, validation, and integration have clear deterministic boundaries. Multiple autonomous agents would complicate authority and auditability without measured benefit. |
| MCP integrations | Not applicable | The only required external tool is the mock target API. A real connector should use the client's authentication and integration contract before selecting an MCP or direct API adapter. |
| Customer outcome ownership | Implemented in delivery package | Local runbook, demo narrative, measurable gates, known limitations, rollback behavior, and production roadmap make the solution reviewable by implementation and engineering stakeholders. |

## Interview position

MigrateFlow uses AI where semantic judgment helps and deterministic software where correctness, authority, and reversibility matter. The strongest FDE decision is the boundary: a model may recommend a mapping, but it cannot invent required identity data, bypass validation, approve ambiguity, or write unreviewed invalid records. New techniques should be added only after a customer requirement and evaluation demonstrate that they improve the outcome.
