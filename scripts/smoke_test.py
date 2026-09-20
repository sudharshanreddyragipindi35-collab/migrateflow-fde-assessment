from __future__ import annotations

import argparse
import json
import time
import uuid
import urllib.error
import urllib.request


def request_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 60.0,
) -> object:
    headers = {"Content-Type": content_type} if content_type else {}
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def multipart_csv(filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"migrateflow-smoke-{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Transactional MigrateFlow API smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--live-model",
        action="store_true",
        help="Use the configured LLM instead of the fast deterministic test adapter",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    health = request_json("GET", f"{base}/health", timeout=args.timeout)
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise RuntimeError(f"Unexpected health response: {health}")
    runtime = request_json("GET", f"{base}/api/system/model", timeout=args.timeout)
    if args.live_model and (not isinstance(runtime, dict) or runtime.get("status") != "ready"):
        raise RuntimeError(f"Configured model is not ready: {runtime}")

    csv = (
        b"employee_id,first_name,last_name,email,hire_date,department,employment_status\n"
        b"SMOKE001,Ada,Lovelace,ada.smoke@example.test,2024-01-15,Engineering,Active\n"
    )
    if args.live_model:
        # This broad label is deliberately excluded from the deterministic fast
        # path, so a live smoke cannot pass without actually exercising inference.
        csv = csv.replace(b"hire_date", b"start_date")
    body, content_type = multipart_csv("smoke_employees.csv", csv)
    created = request_json(
        "POST", f"{base}/api/batches", body=body, content_type=content_type, timeout=args.timeout
    )
    if not isinstance(created, dict) or not created.get("batch_id"):
        raise RuntimeError(f"Batch creation failed: {created}")
    batch_id = str(created["batch_id"])

    mapping_url = f"{base}/api/batches/{batch_id}/mapping-proposals"
    if not args.live_model:
        mapping_url += "?fallback=true"
    proposals = request_json("POST", mapping_url, body=b"", timeout=args.timeout)
    if not isinstance(proposals, list) or not proposals:
        raise RuntimeError("Mapping proposal smoke stage returned no proposals")
    if args.live_model and not any(item.get("provider") == runtime.get("mode") for item in proposals):
        raise RuntimeError("No proposal came from the configured live model; fallback is not a live-model pass")

    workflow = request_json(
        "POST", f"{base}/api/batches/{batch_id}/workflow/start", body=b"", timeout=args.timeout
    )
    if not isinstance(workflow, dict):
        raise RuntimeError(f"Unexpected workflow response: {workflow}")
    if workflow.get("status") == "PAUSED":
        escalations = request_json("GET", f"{base}/api/batches/{batch_id}/escalations", timeout=args.timeout)
        if not isinstance(escalations, list):
            raise RuntimeError("Escalation response was not a list")
        for item in escalations:
            if item.get("status") != "OPEN":
                continue
            if "APPROVE" not in item.get("allowed_actions", []) or not item.get("suggestion"):
                raise RuntimeError(f"Smoke mapping requires an unsafe manual correction: {item}")
            decision = json.dumps({"action": "APPROVE", "actor": "smoke-test"}).encode()
            workflow = request_json(
                "POST",
                f"{base}/api/escalations/{item['escalation_id']}/resolve",
                body=decision,
                content_type="application/json",
                timeout=args.timeout,
            )
    if not isinstance(workflow, dict) or workflow.get("status") != "COMPLETED":
        raise RuntimeError(f"Workflow did not complete: {workflow}")

    records = request_json(
        "POST", f"{base}/api/batches/{batch_id}/records/transform", body=b"", timeout=args.timeout
    )
    if not isinstance(records, list) or not records or any(item.get("status") != "VALID" for item in records):
        raise RuntimeError(f"Smoke record was not valid: {records}")
    pushes = request_json(
        "POST", f"{base}/mock-target/migrations/{batch_id}/push-valid", body=b"", timeout=args.timeout
    )
    if not isinstance(pushes, list) or not pushes or any(item.get("status") != "SUCCESS" for item in pushes):
        raise RuntimeError(f"Target push failed: {pushes}")
    rollback = request_json("DELETE", f"{base}/mock-target/migrations/{batch_id}", timeout=args.timeout)
    if not isinstance(rollback, dict) or rollback.get("rolled_back") != len(pushes):
        raise RuntimeError(f"Rollback did not compensate every smoke write: {rollback}")

    provider = runtime.get("provider") if isinstance(runtime, dict) else "unknown"
    mapping_mode = "live" if args.live_model else "deterministic-test"
    print(
        f"SMOKE PASS batch={batch_id} provider={provider} mapping_mode={mapping_mode} "
        f"proposals={len(proposals)} records={len(records)} pushed={len(pushes)} "
        f"rolled_back={rollback['rolled_back']} elapsed_seconds={time.perf_counter() - started:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
