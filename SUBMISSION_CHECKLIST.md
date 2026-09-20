# MigrateFlow submission checklist

Selected route: **hosted prototype + source repository + one-page approach**. The user is not preparing a video. Local setup remains documented for reproducibility.

## Submission artifacts

- [x] README covers the implemented tech stack, Docker/native setup, Ollama, configuration, workflow, tests and limitations.
- [x] APPROACH.md explains the approach, independent decisions, escalation boundary and next steps (410 words).
- [x] docs/APPROACH_ONE_PAGE.html provides the same text in an A4 print layout.
- [x] A4 write-up layout visually checked to fit one page.
- [ ] Publish full source to the separate migrateflow-fde-assessment repository and verify access.
- [x] Hosted HTTPS URL added to README; browser upload, escalation correction, continuation, delivery and undo verified.
- [ ] Walk through multi-file upload, uncertainty resolution in the UI, automatic continuation and delivery on the hosted application.
- [ ] Ensure the evaluation panel can access both the prototype and repository.

## Recorded implementation evidence

The following are previous recorded checks, not tests rerun during the documentation update. See docs/CURRENT_VALIDATION.md for scope and limitations.

- [x] Background Autopilot, review pause/resumption and mock delivery covered by tests.
- [x] Backend: 62 passing tests, Ruff and mypy.
- [x] Frontend: 13 passing tests, ESLint and TypeScript/Vite build.
- [x] Open-source Ollama smoke included actual model inference, validation, delivery and undo.
- [x] Retry, idempotency, collision safeguards, preserved human decisions and batch-scoped undo covered by regressions.
- [x] CI workflow included; remote run was not verified in the prior session.

## Before sharing

- [ ] Inspect staged files: exclude credentials, local databases, uploads, caches and real client data.
- [ ] Clearly distinguish proposed production infrastructure from implemented controls in design documents.
- [ ] Record fresh hosted verification results without presenting local tests as hosted proof.

DEMO_SCRIPT.md remains an optional live walkthrough guide. A recording applies if the submission switches back to the assignment's local-run route.

