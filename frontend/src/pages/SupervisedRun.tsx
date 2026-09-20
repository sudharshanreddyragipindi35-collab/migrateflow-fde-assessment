import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { WorkflowEvent, WorkflowStatus } from "../types";
import { StatusPill } from "../components/StatusPill";
import { friendlyWorkflowMessage } from "../utils/workflow";

export function SupervisedRun({ batchId, onReview, onPreview }: { batchId: string; onReview: () => void; onPreview: () => void }) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [connection, setConnection] = useState("Connecting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);

  useEffect(() => {
    if (!batchId) return;
    api.status(batchId).then(setWorkflowStatus).catch(() => setWorkflowStatus(null));
  }, [batchId]);

  useEffect(() => {
    if (!batchId) return;
    const stream = new EventSource(api.eventUrl(batchId));
    stream.onopen = () => setConnection("Live");
    const add = (event: Event) => setEvents((current) => {
      const incoming = JSON.parse((event as MessageEvent).data) as WorkflowEvent;
      return current.some((item) => item.event_id === incoming.event_id) ? current : [...current, incoming];
    });
    ["node_started", "node_completed", "progress", "workflow_paused", "workflow_resumed", "reconciliation_completed", "record_validated", "push_result", "rollback", "workflow_failed"].forEach((type) => stream.addEventListener(type, add));
    stream.onerror = () => setConnection("Reconnecting");
    return () => stream.close();
  }, [batchId]);

  async function run() {
    setBusy(true);
    setError("");
    try {
      if (workflowStatus?.status === "PAUSED") {
        onReview();
        return;
      }
      if (workflowStatus?.status === "COMPLETED") {
        const records = await api.records(batchId);
        if (records.length) {
          onPreview();
          return;
        }
        await api.transform(batchId);
        const transformed = await api.status(batchId);
        if (transformed.status === "PAUSED") onReview(); else onPreview();
        return;
      }
      await api.propose(batchId);
      const workflow = await api.start(batchId);
      setWorkflowStatus(workflow);
      if (workflow.status === "PAUSED") {
        onReview();
      } else {
        await api.transform(batchId);
        const transformed = await api.status(batchId);
        if (transformed.status === "PAUSED") onReview(); else onPreview();
      }
    } catch (reason) {
      setError(friendlyWorkflowMessage(reason instanceof Error ? reason.message : "The workflow could not start safely."));
    } finally {
      setBusy(false);
    }
  }

  const latestWorkflowState = events.filter((event) => ["workflow_paused", "workflow_resumed"].includes(event.event_type)).at(-1);
  const paused = workflowStatus?.status === "PAUSED" || latestWorkflowState?.event_type === "workflow_paused";
  const lastEvent = events.at(-1);
  const retryingFailure = lastEvent?.event_type === "workflow_failed";
  const actionLabel = workflowStatus?.status === "PAUSED" ? "Continue review" : workflowStatus?.status === "COMPLETED" ? "View results" : retryingFailure ? "Retry safely" : "Generate mappings and start";
  return <section><div className="section-heading"><div><p className="eyebrow">Step 2 of 5</p><h2>Analyze and map</h2></div><StatusPill value={paused ? "PAUSED" : connection.toUpperCase()} /></div>{paused && <div className="pause-banner" role="status"><strong>Next step: review decisions</strong><span>Analysis is complete and the workflow is safely paused. Open Step 3 to confirm uncertain mappings or values.</span></div>}{error && <p role="alert" className="error">{error}</p>}{!batchId ? <div className="empty"><h3>No active migration</h3><p>Complete Step 1: upload CSV or Excel files to begin.</p></div> : <><div className="run-controls"><div><strong>{retryingFailure ? "Safe retry available" : "Ready for Step 2"}</strong><p>{retryingFailure ? "The previous attempt changed no data. Retry once; if the model response is still incomplete, supervised fallback proposals will be sent to Step 3 for review." : "Select the button to analyze columns and propose target mappings. Nothing is pushed during this step."}</p></div><button className="primary" disabled={busy} onClick={run}>{busy ? "Analyzing securely…" : actionLabel}</button></div><ol className="timeline">{events.map((event) => <li key={event.event_id}><span>{new Date(event.timestamp).toLocaleTimeString()}</span><div><strong>{event.event_type.replaceAll("_", " ")}</strong>{event.event_type === "workflow_failed" ? <p>{friendlyWorkflowMessage(String(event.payload.message ?? "The workflow stopped safely."))}</p> : <pre>{JSON.stringify(event.payload)}</pre>}</div></li>)}</ol></>}</section>;
}
