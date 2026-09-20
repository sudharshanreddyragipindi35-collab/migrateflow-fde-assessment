from __future__ import annotations

import argparse
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def one_request(url: str, timeout: float) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            ok = 200 <= response.status < 400
    except (urllib.error.URLError, TimeoutError):
        ok = False
    return (time.perf_counter() - started) * 1000, ok


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percent)))
    return ordered[index]


def run_phase(url: str, users: int, requests_per_user: int, timeout: float) -> dict[str, float | int]:
    total = users * requests_per_user
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        futures = [pool.submit(one_request, url, timeout) for _ in range(total)]
        results = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started
    latencies = [latency for latency, _ in results]
    failures = sum(not ok for _, ok in results)
    return {
        "requests": total,
        "users": users,
        "rps": total / elapsed,
        "mean_ms": statistics.fmean(latencies),
        "p95_ms": percentile(latencies, 0.95),
        "errors": failures,
        "error_rate": failures / total,
    }


def print_phase(name: str, result: dict[str, float | int]) -> None:
    print(
        f"phase={name} requests={result['requests']} users={result['users']} "
        f"rps={result['rps']:.2f} mean_ms={result['mean_ms']:.2f} "
        f"p95_ms={result['p95_ms']:.2f} errors={result['errors']} "
        f"error_rate={result['error_rate']:.4f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded read-only MigrateFlow load and spike test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--requests-per-user", type=int, default=5)
    parser.add_argument("--pattern", choices=["steady", "spike"], default="steady")
    parser.add_argument("--baseline-users", type=int, default=5)
    parser.add_argument("--baseline-requests-per-user", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=750.0)
    args = parser.parse_args()
    values = [args.users, args.baseline_users]
    request_values = [args.requests_per_user, args.baseline_requests_per_user]
    if any(not 1 <= value <= 10_000 for value in values) or any(
        not 1 <= value <= 1_000 for value in request_values
    ):
        parser.error("user counts must be 1..10000 and requests-per-user must be 1..1000")

    url = f"{args.base_url.rstrip('/')}/{args.path.lstrip('/')}"
    if args.pattern == "spike":
        baseline = run_phase(url, args.baseline_users, args.baseline_requests_per_user, args.timeout)
        print_phase("baseline", baseline)
    result = run_phase(url, args.users, args.requests_per_user, args.timeout)
    print_phase(args.pattern, result)
    return int(
        float(result["error_rate"]) > args.max_error_rate
        or float(result["p95_ms"]) > args.max_p95_ms
    )


if __name__ == "__main__":
    raise SystemExit(main())
