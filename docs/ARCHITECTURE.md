# MigrateFlow Architecture

## System boundary

MigrateFlow is a supervised migration system with a FastAPI backend, React consultant interface, a SQLite local profile, and Ollama or Anthropic model adapters. A SQL-backed finite-state workflow owns durable orchestration, policy, and human decisions. A LangGraph contract models the policy/interrupt topology and is tested independently; it is not presented as the runtime source of truth. The production target uses stateless API replicas behind a load balancer with PostgreSQL, private object storage, and separately scalable workers.

## Components

1. Ingestion parses bounded CSV and XLSX uploads into immutable source records and masked profiles.
2. Mapping combines deterministic evidence with optional structured model proposals.
3. The autonomy policy decides whether a proposal is safe to apply or must pause for a person.
4. Cleaning and validation produce canonical records with field-level provenance.
5. Integration writes approved records with idempotency keys and batch-scoped compensation.
6. Audit storage records material actions as append-only events.

## Ownership decisions

- Deterministic policy controls autonomy.
- Application tables own durable pause and resume so API queries, audits, and decisions share one transaction boundary.
- LangGraph documents and tests the agent transition contract; adopting it at runtime requires a shared production checkpointer and removal of duplicate workflow state.
- SQLite owns durable application state.
- Audit entries are append only.
- Ollama is the default local model path; Anthropic is an optional configured provider.
- Mock mode is explicit and may not imitate model intelligence.

## Data flow

Uploaded files are stored outside public paths under generated batch identifiers. Only bounded column metadata, aggregate statistics, and masked examples may reach a model. Raw records remain in deterministic processing paths. Target writes occur only after mapping, validation, and approval gates pass.

Detailed decisions and capacity assumptions are in `HIGH_LEVEL_DESIGN.md`, `LOW_LEVEL_DESIGN.md`, `SCALABILITY_AND_CAPACITY.md`, and `GENAI_ENGINEERING.md`.
