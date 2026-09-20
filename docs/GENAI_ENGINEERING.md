# GenAI Engineering Design

## Capabilities deliberately implemented

MigrateFlow uses generative AI only for semantic schema suggestions. The advanced engineering is in control of the model, not in maximizing model autonomy.

- Provider abstraction supports private Ollama and Anthropic without changing policy logic.
- Semantic proposals are batched once per source file, reducing model round trips while validating response count and preserving deterministic per-column scoring.
- Pydantic structured output rejects malformed proposals.
- Data minimization sends masked, bounded column profiles instead of raw employee rows.
- Prompt-injection filtering redacts instruction-like file names, column names, and samples and tells the model to treat context as data.
- Composite confidence combines model confidence with deterministic name, alias, type, pattern, and uniqueness evidence.
- Human-in-the-loop gates ambiguous dates, low confidence, unmapped fields, and collisions.
- Durable SQL state supports pause and resume while a tested LangGraph contract makes the intended interrupt topology explicit.
- Explicit fallback, timeout, retry, and failure states prevent silent imitation of model intelligence.
- Evaluation cases, provider labels, audit events, and provenance make quality inspectable.

## Production additions

Use a model gateway or shared limiter for quotas, token budgets, redaction, request IDs, latency, and cost metrics. Record model name, prompt-template version, token counts, latency, outcome class, and redacted error category; do not log prompts containing client data. Use prompt caching for stable instructions and target schemas when supported and beneficial. Maintain an offline golden set and run regression evaluations before changing model or prompt version.

## Techniques intentionally excluded

RAG, vector databases, conversational memory, autonomous web tools, multi-agent delegation, and free-form code execution are not required for bounded column mapping. Adding them would expand cost and attack surface without improving the defined workflow. They should be introduced only for a measured use case with separate authorization, evaluation, and threat modeling.

## Anthropic configuration

Keep the key empty in source control:

```dotenv
MODEL_MODE=anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

Add the real key only to the local untracked `.env` or a production secret manager. The adapter fails closed when the key is blank. Provider rate limits and model lifecycle are deployment dependencies, so model identifiers and quotas must be checked during release readiness.
