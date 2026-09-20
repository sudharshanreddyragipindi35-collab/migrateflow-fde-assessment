# Current validation â€” 20 September 2026

The five reproduced submission-review failures have regression coverage and are repaired. Autopilot now runs in a persisted background queue, resumes after review and sends valid records under the permission established at upload. Guided mode retains manual sending.

| Check | Fresh result |
|---|---|
| Backend Ruff | Passed |
| Backend mypy | Passed, 47 source files |
| Backend pytest | 62 passed; 7 third-party Pydantic deprecation warnings |
| Frontend ESLint | Passed |
| Frontend Vitest | 13 passed across 4 files |
| TypeScript/Vite build | Passed |
| Deterministic evaluation | Six mapping cases, six date cases and three reconciliation cases; measured correctness metrics passed |
| Real HTTP supervised smoke | Passed: upload, mapping, validation, delivery and undo |
| Real HTTP Autopilot probe | Three independent single-record runs completed without review or browser-driven advancement; each write was undone |
| Browser walkthrough | Not performed: the browser tool reported no available browser |
| Fresh Ollama inference | Passed with qwen2.5:7b-instruct on CPU: 7 proposals, including a real model proposal; validation, delivery and undo completed in 39.70 seconds |
| Docker build and local deployment | Both updated images built; API healthy and UI HTTP 200 |
| Production replicas / cloud CI | Not rerun or deployed during this change |

## Measured responsiveness

From `evaluation/runtime_report.json`, on this machine in fallback mode:

| Run | Upload response | Automatic completion |
|---|---:|---:|
| 1 | 120.93 ms | 845.74 ms |
| 2 | 106.75 ms | 1096.10 ms |
| 3 | 152.19 ms | 1035.32 ms |

Completion includes worker dispatch and polling. This is a small sequential responsiveness probe, not a throughput, production SLA, live-model accuracy or competitor benchmark. The fast-path regression separately verifies that two recognized columns bypass inference while one unfamiliar column reaches the model.

## Correctness evidence

`backend/tests/test_submission_regressions.py` verifies impossible dates, unambiguous date cleanup, rejection with multiple errors, preservation of human decisions on replay, target review/cancellation gates, collision rejection, partial failure/retry/undo status, inference routing, atomic lease recovery, unattended execution, review resumption, multi-file reconciliation/delivery, cancellation during analysis, named model-result alignment, accurate metric denominators, sample privacy and resource limits.

`frontend/tests/IntegrationAudit.test.tsx` verifies useful failure guidance, retry success, visible API errors and disabled retry after undo. Existing upload and review component tests continue to pass.

## Before submission

1. Use `docker-compose.assessment.yml` with the main Compose file for the verified CPU configuration. `python scripts/smoke_test.py --live-model --timeout 180` passed and requires a proposal from the configured provider; fallback or an all-alias fast path cannot be misreported as live inference. The first unbounded streaming attempt fell back; the successful revision caps generation, uses non-streaming requests and narrows date-only context. The 29 mapping/workflow regressions passed again after that adjustment.
2. The user selected the hosted-link route. Add and verify the hosted application URL, including at least one human escalation resolved in the UI. DEMO_SCRIPT.md is an optional walkthrough guide; no recording is planned for this route.
3. Check the rendered one-page approach and visual layout, and include the new source/test/CI files in the submitted Git repository. Temporary databases/uploads are excluded.

See `REQUIREMENTS_AND_VERIFICATION.md` for functional and non-functional coverage and explicit production follow-ups. The earlier submission review is retained as a historical record, not the current verdict.


## Hosted AWS verification — 20 September 2026

Live URL: https://demo-migrateflow.51-21-247-103.sslip.io. Frontend, backend and local Ollama run on the separate EC2 assessment instance behind Caddy HTTPS. Root storage was expanded to 30 GiB and its XFS filesystem enlarged.

- HTTPS certificate obtained; frontend, API and model containers healthy.
- Headless Chrome UI walkthrough passed: synthetic upload, two UI review resolutions including a date correction, automatic delivery of one record, and undo via the UI; zero JavaScript page errors. Screenshot of the review screen visually inspected. See evaluation/aws_ui_report.json.
- Real Ollama HTTP smoke passed in 123.50 seconds: seven proposals, including configured-provider inference, one validated record, one successful push and one undo. See evaluation/aws_live_model_report.json.
- Initial 60-second inference requests timed out and fell back. Final hosted configuration uses single-request model concurrency and a bounded 180-second timeout. Do not present desktop 39.70-second results as hosted latency.
- Initial source GitHub Actions run passed: https://github.com/sudharshanreddyragipindi35-collab/migrateflow-fde-assessment/actions/runs/35506110569. Subsequent documentation/deployment commits may trigger separate checks.
- Approach A4 HTML visually inspected and fits one page.

These checks supersede the earlier browser-unavailable and remote-CI-not-verified entries for the tested paths only. They do not establish multi-user isolation, load capacity or production security. Use synthetic data in the shared demo. See docs/AWS_DEPLOYMENT_STATUS.md for operations, cost and hostname stability limits.
