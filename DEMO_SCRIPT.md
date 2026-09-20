# MigrateFlow Demo Script

## 0:00 to 0:35 Problem and boundary

Open the New Migration view. Show the Autopilot and Human-in-the-loop choices. Explain that both use the same safety policy: Autopilot adds agent-to-agent tracking and removes routine clicks, while Human-in-the-loop retains the original supervised five-step flow. Explain that starting Autopilot authorizes sending valid records to the demo destination; guided mode waits for a separate send decision.

## 0:35 to 1:05 Multiple source files

Choose Autopilot. Drag in `employees_india.csv`, `employee_master.xlsx`, and `new_joiners.csv` together. Show the filename and size list and the employee target contract. Start the migration and move to the Agent Pipeline.

## 1:05 to 1:45 Automatic mapping and pause

Watch Upload agent receive a tick, Analyze agent recognize familiar fields immediately and use the local open-source Ollama model for unfamiliar fields, and Review agent apply safe mappings automatically. Show obvious aliases such as Employee ID, Work Email, and Department. Pause on the genuine mapping ambiguity around `start_date`, proving that Autopilot is bounded rather than reckless.

## 1:45 to 2:30 Human correction and resume

Open Review Queue. Show masked context, recommendation, alternatives, confidence components, and the reason code. Select `hire_date`, choose Correct, and submit. The agent then transforms and reconciles the files. Point out that the overlapping `IN001` source rows merged automatically while invalid record fields returned to the same queue. Correct `employee_id` from `202` to `EM202`, and explain why invalid values cannot simply be approved.

## 2:30 to 3:15 Cleanup and validation

Resolve or reject the remaining record cases, then open Data Preview. Filter between Valid and Rejected. Compare original and transformed values, including trimmed text and lowercased email. Show the reconciled `IN001` record with both source filenames and point out field-level provenance. Explain that ambiguous or missing required values were never guessed.

## 3:15 to 4:05 Push retry and rollback

After the final review, watch Autopilot send valid records automatically with DEMO_FAILURES=true. Open Integration Audit. Show the deliberate retryable result for `retry.noah@example.test`, select Retry failed records, and confirm success with retry count one. Open the audit chronology or JSON export. Choose Undo sent records, acknowledge the confirmation, and show only this batch moving to Rolled Back.

## 4:05 to 4:30 Evidence and close

Open `/docs` briefly to show the API contract. Finish with the implementation checklist and final validation report: backend and frontend quality gates, supervised end-to-end test, Docker health check, PII and injection tests, and evaluation metrics.
