import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Escalation, ExecutionMode } from "../types";

const FIELD_LABELS: Record<string, string> = {
  employee_id: "Employee ID",
  first_name: "First name",
  last_name: "Last name",
  email: "Email address",
  phone: "Phone number",
  date_of_birth: "Date of birth",
  hire_date: "Hire date",
  department: "Department",
  employment_status: "Employment status",
  manager_id: "Manager ID",
  source_system: "Source system",
};

const REASON_LABELS: Record<string, string> = {
  MODEL_RECOVERY_FALLBACK: "Confirm safe fallback mapping",
  MODEL_BATCH_RETRY: "Confirm recovered model mapping",
  PROVIDER_FAILOVER: "Confirm Claude failover mapping",
  CONFIDENCE_REVIEW: "Confirm suggested mapping",
  LOW_CONFIDENCE_UNMAPPED: "Choose the correct target field",
  AMBIGUOUS_DATE: "Confirm the date meaning",
  TARGET_COLLISION: "Resolve duplicate target mapping",
};

function fieldLabel(field?: string) {
  if (!field) return "Value";
  return FIELD_LABELS[field] ?? field.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase());
}

function friendlyError(field: string | undefined, message: string) {
  if (field?.endsWith("_date") || field === "date_of_birth") {
    return `${fieldLabel(field)}: enter a real date in YYYY-MM-DD format, for example 2024-01-15.`;
  }
  if (field === "employee_id" && message.toLowerCase().includes("string")) {
    return "Employee ID: enter an ID as text, for example EM202.";
  }
  const detail = message.includes(":") ? message.split(":").slice(1).join(":").trim() : message;
  return `${fieldLabel(field)}: ${detail}`;
}

export function ReviewQueue({ batchId, onCompleted, onPreview = onCompleted }: { batchId: string; onCompleted: () => void; onPreview?: () => void }) {
  const [items, setItems] = useState<Escalation[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [correction, setCorrection] = useState<Record<string, string>>({});
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("HUMAN_IN_LOOP");

  const refresh = useCallback(async () => {
    if (!batchId) return;
    const all = await api.escalations(batchId);
    setItems(all.filter((item) => item.status === "OPEN"));
  }, [batchId]);

  useEffect(() => {
    if (!batchId) return;
    api.pipeline(batchId).then((result) => setExecutionMode(result.execution_mode)).catch(() => undefined);
    api.escalations(batchId)
      .then((all) => setItems(all.filter((item) => item.status === "OPEN")))
      .catch((reason: Error) => setError(reason.message));
  }, [batchId]);

  async function decide(item: Escalation, action: string) {
    if (busy) return;
    const value = correction[item.escalation_id];
    if (action === "CORRECT" && !value) {
      setError("Enter or choose a corrected value before continuing.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      const workflow = await api.resolve(item.escalation_id, action, value);
      const recordReview = item.source_context.kind?.startsWith("record_") ?? false;
      if (workflow.status === "COMPLETED") {
        if (executionMode === "HUMAN_IN_LOOP" && !recordReview) {
          await api.transform(batchId);
          const transformed = await api.status(batchId);
          if (transformed.status === "COMPLETED") {
            onPreview();
            return;
          }
          await refresh();
          return;
        }
        if (executionMode === "HUMAN_IN_LOOP") {
          onPreview();
          return;
        }
        onCompleted();
        return;
      }
      await refresh();
    } catch (reason) {
      setError(friendlyError(item.source_context.field, reason instanceof Error ? reason.message : "The correction could not be saved."));
    } finally { setBusy(false); }
  }

  if (!batchId || (!items.length && !error)) {
    return <section><div className="section-heading"><div><p className="eyebrow">Supervision</p><h2>Review queue</h2></div></div><div className="empty"><h3>Nothing needs review</h3><p>Start mapping from Live run. Ambiguous mappings, duplicate conflicts, and records that fail validation twice will appear here.</p></div></section>;
  }

  return <section>
    <div className="section-heading"><div><p className="eyebrow">Supervision</p><h2>Review queue</h2></div><span>{items.length} open</span></div>
    {error && <p role="alert" className="error">{error}</p>}
    <p>Only uncertain items appear here. Approve a verified match, save the correct value, or exclude an item you cannot verify. Safe items continue automatically.</p>
    {busy && <p role="status">Saving your decision…</p>}
    <fieldset disabled={busy} style={{ border: 0, padding: 0, minWidth: 0 }}><legend className="sr-only">Review decisions</legend><div className="card-grid">{items.map((item) => {
      const context = item.source_context;
      const recordReview = context.kind?.startsWith("record_") ?? false;
      const can = (action: string) => item.allowed_actions.includes(action);
      const alternatives = [...new Set(item.alternatives.filter(Boolean))];
      const correctionOptions = [...new Set([item.suggestion, ...alternatives, ...(!recordReview ? Object.keys(FIELD_LABELS) : [])].filter((value): value is string => Boolean(value)))];
      const isDateCorrection = recordReview && (context.field?.endsWith("_date") || context.field === "date_of_birth");
      const correctionId = `correction-${item.escalation_id}`;
      const helpId = `correction-help-${item.escalation_id}`;
      const displayName = fieldLabel(recordReview ? context.field : context.source_column);
      return <article className="review-card" key={item.escalation_id}>
        <div className="card-top"><span>{context.source_file}{context.source_record_id ? ` - row ${context.source_record_id}` : ""}</span><strong>{recordReview ? "Action required" : REASON_LABELS[item.reason_code] ?? item.reason_code.replaceAll("_", " ")}</strong></div>
        <h3>{displayName}</h3>
        <p>{recordReview ? "Current value" : "Recommended target"}: <code>{String(context.current_value ?? item.suggestion ?? "Missing")}</code></p>
        {!!context.samples?.length && <p>Source examples: {context.samples.map((sample) => String(sample ?? "Empty")).join(" · ")}</p>}
        {context.explanation && <p>{context.explanation}</p>}
        {context.conflicting_values && Object.keys(context.conflicting_values).length > 0 && <div><strong>These records disagree:</strong><ul>{Object.entries(context.conflicting_values).map(([field, values]) => <li key={field}>{fieldLabel(field)}: {values.map((value) => String(value)).join(" compared with ")}</li>)}</ul><p>Keep both only if they are different employees with verified unique IDs. Otherwise exclude this duplicate.</p></div>}
        {context.errors?.length ? <ul className="review-errors">{context.errors.map((message) => <li key={message}>{friendlyError(context.field, message)}</li>)}</ul> : null}
        {!recordReview && <div className="confidence">{Object.entries(item.confidence_evidence).map(([key, value]) => <label key={key}><span>{key.replaceAll("_", " ")}</span><progress max="1" value={value} /><small>{Math.round(value * 100)}%</small></label>)}</div>}
        {!recordReview && item.reason_code === "MODEL_RECOVERY_FALLBACK" && <p className="review-explanation">Ollama did not return a complete structured response after retrying. MigrateFlow generated this safe suggestion from column names and data types. Confirm or correct it before continuing.</p>}
        {!recordReview && item.reason_code === "PROVIDER_FAILOVER" && <p className="review-explanation">Ollama did not return a valid response after retrying. Claude generated this suggestion. Confirm or correct it before continuing.</p>}
        {!recordReview && item.reason_code === "TARGET_COLLISION" && <p className="review-explanation">Two columns want to fill the same destination field. Approve the correct source, then reject the other mapping or choose a different field. Values will never be silently overwritten.</p>}
        {recordReview && <p className="review-explanation">Automatic validation could not safely fix this value. Enter the verified value below, or reject the record if you cannot confirm it.</p>}
        {can("CORRECT") && <div className="correction-field"><label htmlFor={correctionId}>{recordReview ? `Corrected ${displayName}` : "Choose the correct target field"}</label>
          {recordReview && !alternatives.length
            ? <><input id={correctionId} aria-describedby={isDateCorrection ? helpId : undefined} type={isDateCorrection ? "date" : "text"} value={correction[item.escalation_id] ?? ""} onChange={(event) => setCorrection({ ...correction, [item.escalation_id]: event.target.value })} placeholder={isDateCorrection ? "YYYY-MM-DD" : `Example: ${context.field === "employee_id" ? "EM202" : `correct ${displayName.toLowerCase()}`}`} />{isDateCorrection && <p id={helpId} className="format-help"><strong>Required format: YYYY-MM-DD</strong><span>Example: 2024-01-15 means 15 January 2024.</span><span>If the correct date is unknown, reject the record. Never guess.</span></p>}</>
            : <select id={correctionId} value={correction[item.escalation_id] ?? ""} onChange={(event) => setCorrection({ ...correction, [item.escalation_id]: event.target.value })}><option value="">Select a correction</option>{correctionOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select>}
        </div>}
        <div className="actions">{can("REJECT") && <button onClick={() => decide(item, "REJECT")}>{recordReview ? "Reject record" : "Reject"}</button>}{can("CORRECT") && <button className="primary" onClick={() => decide(item, "CORRECT")}>Save correction</button>}{can("APPROVE") && <button className="primary" onClick={() => decide(item, "APPROVE")}>Approve</button>}</div>
      </article>;
    })}</div></fieldset>
  </section>;
}
