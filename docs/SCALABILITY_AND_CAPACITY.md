# Scalability and Capacity Plan

## Define the user number

Registered users, active sessions, concurrent requests, uploads per minute, rows per file, LLM calls per batch, and target writes per second are different capacity dimensions. This plan uses 2,000 and 10,000 as user-population tiers and supplies explicit concurrency assumptions. Before launch, replace assumptions with observed traffic and rerun the tests.

## Reference tiers

| Tier | Planning assumption | Starting topology | Main gate |
|---|---|---|---|
| Local | 1 to 5 consultants | 1 API, SQLite, local files | Functional tests |
| 2k population | 200 concurrent sessions, 50 non-model RPS, 10 active migrations | 3 to 6 API replicas, 4 to 12 workers, PostgreSQL multi-zone, object storage, Redis or broker | 2x peak for 30 minutes plus 8-hour soak |
| 10k population | 1,000 concurrent sessions, 250 non-model RPS, 50 active migrations | 6 to 30 API replicas, 10 to 100 workers, managed PostgreSQL, queue, Redis, object storage, CDN and WAF | 2x peak, zone failure, provider throttling, recovery test |
| 10k concurrent | Separate stress objective, not implied by 10k registered users | Size from measured service demand; likely multi-region edge and larger pools | Dedicated capacity test and cost approval |

Replica counts are starting hypotheses, not promises. Autoscaling should use request concurrency and latency for APIs, queue age and depth for workers, and provider quotas for LLM workers. CPU alone is insufficient.

## Controls that prevent cascading failure

- Enforce upload byte, file count, row, and decompressed-size limits.
- Return `429` with retry guidance at tenant and user boundaries.
- Bound every external call with timeout, retry budget, jitter, and circuit breaker.
- Apply queue admission limits and dead-letter poison jobs.
- Use bulkheads for parsing, LLM, and target connectors.
- Cap database connections: total replica pools must remain below the database limit.
- Cache target schema and stable prompt prefixes; never cache raw PII responses across tenants.
- Paginate record lists and stream large exports from object storage.
- Degrade deliberately: preserve review and audit access when model generation is unavailable.

## Database pool calculation

For `R` API replicas, pool size `P`, overflow `O`, and `W` worker processes, worst-case connections are approximately `R x (P + O) + worker pools + migration and administration reserve`. Do not deploy the example defaults unchanged at high replica counts. Set a database budget first, reserve at least 20 percent for operations and failover, then divide the remainder across replicas or place a transaction pooler such as PgBouncer in front.

## LLM capacity

Anthropic quotas are independent of API replica count. Limit concurrent model calls centrally, honor `Retry-After`, and track requests per minute plus input and output tokens per minute. Ramp traffic instead of sending a sudden burst. Cache stable prompt prefixes where the selected API path supports it. Batch non-interactive evaluation work; do not batch interactive review requests.

## Load and resilience gates

The safe default command exercises only `GET /health`:

```powershell
python scripts/load_test.py --base-url http://localhost:8080 --users 200 --requests-per-user 20
```

The spike profile establishes a small baseline and then applies an abrupt concurrency jump:

```powershell
python scripts/load_test.py --base-url http://localhost:8080 --pattern spike --baseline-users 10 --users 200 --requests-per-user 5
```

This client-side test is a bounded release signal, not a substitute for distributed load generation, server-side saturation metrics, or an isolated production-scale environment.

Run large tests only in an isolated performance environment with synthetic data and provider spend limits. A release passes when non-model p95 is below 750 ms, server errors stay below 1 percent, database saturation stays below its alert threshold, accepted jobs are not lost, SSE can resume, and batch rollback remains isolated. Also test API replica termination, database failover, queue redelivery, Anthropic 429 and 529 responses, target timeouts, and object-store errors.

## Scale-compose demonstration

Set a strong local password outside source control, then run:

```powershell
$env:POSTGRES_PASSWORD = "replace-locally"
$env:ANTHROPIC_API_KEY = "replace-locally"
docker compose -f docker-compose.production.yml up --build --scale backend=4
```

Open `http://localhost:8080`. This proves routing and process replication on one machine; it does not certify the 2k or 10k tiers.
