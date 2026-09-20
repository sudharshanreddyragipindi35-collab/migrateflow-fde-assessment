import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { PipelineStatus, WorkflowEvent } from "../types";
import { StatusPill } from "../components/StatusPill";
import { friendlyWorkflowMessage } from "../utils/workflow";
import { SupervisedRun } from "./SupervisedRun";

const ICONS: Record<string, string> = {
  COMPLETED: "✓",
  RUNNING: "↻",
  WAITING_APPROVAL: "!",
  NEEDS_REVIEW: "!",
  READY_TO_PUSH: "!",
  FAILED: "×",
  SKIPPED: "−",
  QUEUED: "·",
};

export function LiveRun({ batchId, onReview, onPreview, onAudit }: { batchId: string; onReview: () => void; onPreview: () => void; onAudit: () => void }) {
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [connection, setConnection] = useState("Connecting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const advancing = useRef(false);

  const refresh = useCallback(async () => {
    if (!batchId) return;
    setPipeline(await api.pipeline(batchId));
  }, [batchId]);

  const advance = useCallback(async () => {
    if (!batchId || advancing.current) return;
    advancing.current = true;
    setBusy(true);
    setError("");
    try {
      setPipeline(await api.advancePipeline(batchId));
    } catch (reason) {
      setError(friendlyWorkflowMessage(reason instanceof Error ? reason.message : "The agent stopped safely."));
      await refresh().catch(() => undefined);
    } finally {
      advancing.current = false;
      setBusy(false);
    }
  }, [batchId, refresh]);

  useEffect(() => {
    if (!batchId) return;
    let active = true;
    api.pipeline(batchId).then((result) => {
      if (active) setPipeline(result);
    }).catch((reason: Error) => {
      if (active) setError(reason.message);
    });
    return () => { active = false; };
  }, [batchId]);

  useEffect(() => {
    if (!batchId || pipeline?.execution_mode === "HUMAN_IN_LOOP") return;
    const timer = window.setInterval(() => void refresh().catch(() => setConnection("Reconnecting")), 2000);
    return () => window.clearInterval(timer);
  }, [batchId, pipeline?.execution_mode, refresh]);

  useEffect(() => {
    if (!batchId || pipeline?.execution_mode === "HUMAN_IN_LOOP") return;
    const stream = new EventSource(api.eventUrl(batchId));
    stream.onopen = () => setConnection("Live");
    const add = (event: Event) => {
      const incoming = JSON.parse((event as MessageEvent).data) as WorkflowEvent;
      setEvents((current) => current.some((item) => item.event_id === incoming.event_id) ? current : [...current, incoming]);
      if (incoming.event_type.startsWith("agent_")) void refresh();
    };
    ["agent_started", "agent_completed", "agent_waiting", "agent_failed", "workflow_paused", "workflow_resumed", "push_result", "rollback", "workflow_failed"].forEach((type) => stream.addEventListener(type, add));
    stream.onerror = () => setConnection("Reconnecting");
    return () => stream.close();
  }, [batchId, pipeline?.execution_mode, refresh]);

  if (pipeline?.execution_mode === "HUMAN_IN_LOOP") {
    return <SupervisedRun batchId={batchId} onReview={onReview} onPreview={onPreview} />;
  }

  async function stop() {
    if (!window.confirm("Stop the remaining work? Any records already sent can be undone from Results.")) return;
    try { setPipeline(await api.cancelPipeline(batchId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not stop this migration."); }
  }

  async function decidePush(decision: "PUSH" | "DO_NOT_PUSH") {
    setBusy(true);
    setError("");
    try {
      const result = await api.decidePush(batchId, decision);
      setPipeline(result);
      if (decision === "PUSH") onAudit();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The push decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (!batchId) return <section><div className="section-heading"><div><p className="eyebrow">Agent orchestration</p><h2>Migration pipeline</h2></div></div><div className="empty"><h3>No active migration</h3><p>Upload CSV or Excel files and choose Autopilot or Human-in-the-loop to begin.</p></div></section>;

  const current = pipeline?.stages.find((stage) => stage.stage_id === pipeline.current_stage);
  const needsReview = current?.status === "NEEDS_REVIEW";
  const readyToPush = pipeline?.execution_mode !== "AUTOPILOT" && (current?.status === "READY_TO_PUSH" || (current?.stage_id === "push" && current.status === "FAILED"));
  const canAdvance = current?.status === "WAITING_APPROVAL" || (current?.status === "FAILED" && pipeline?.status !== "PARTIAL_FAILURE");
  const terminal = ["CANCELLED", "COMPLETED", "COMPLETED_WITHOUT_PUSH", "ROLLED_BACK", "PARTIAL_FAILURE"].includes(pipeline?.status ?? "");

  return <section>
    <div className="section-heading"><div><p className="eyebrow">Agent orchestration</p><h2>Migration pipeline</h2></div><div className="pipeline-heading-status"><StatusPill value={pipeline?.status ?? connection.toUpperCase()} />{pipeline && <span className={`mode-badge ${pipeline.execution_mode.toLowerCase()}`}>{pipeline.execution_mode === "AUTOPILOT" ? "Autopilot" : "Human-in-the-loop"}</span>}</div></div>
    {error && <p role="alert" className="error">{error}</p>}
    {pipeline && <>
      <div className="pipeline-summary" role="status"><strong>{pipeline.action_message}</strong><span>{pipeline.execution_mode === "AUTOPILOT" ? "We match fields, clean records and send valid employees to the demo destination automatically. Only uncertain cases need your help. Work continues if you close this page." : "Review each step before sending records."}</span></div>
      <ol className="agent-pipeline" aria-label="Agent pipeline">{pipeline.stages.map((stage, index) => <li key={stage.stage_id} className={`${stage.status.toLowerCase().replaceAll("_", "-")} ${stage.stage_id === pipeline.current_stage ? "current" : ""}`}>
        <div className="agent-connector" aria-hidden="true" />
        <span className={`agent-status-icon ${stage.status === "RUNNING" ? "spinning" : ""}`}>{ICONS[stage.status] ?? index + 1}</span>
        <div><p>{stage.agent}</p><h3>{stage.title}</h3><span>{stage.description}</span><small>{stage.detail}</small></div>
        <StatusPill value={stage.status} />
      </li>)}</ol>
      <div className="pipeline-actions">
        {canAdvance && <button className="primary" disabled={busy} onClick={() => void advance()}>{busy ? `${current?.agent} is working…` : current?.status === "FAILED" ? `Retry ${current.agent}` : `Approve and run ${current?.agent}`}</button>}
        {needsReview && <button className="primary" onClick={onReview}>Open required review</button>}
        {readyToPush && <><button onClick={onPreview}>Review validated data</button><button className="primary" disabled={busy} onClick={() => void decidePush("PUSH")}>Push approved records</button><button className="danger" disabled={busy} onClick={() => void decidePush("DO_NOT_PUSH")}>Do not push</button></>}
        {["COMPLETED", "PARTIAL_FAILURE", "ROLLED_BACK"].includes(pipeline.status) && <button className="primary" onClick={onAudit}>View results and undo options</button>}
        {!terminal && <button onClick={() => void stop()}>Stop migration</button>}
      </div>
    </>}
    <details className="agent-events"><summary>Technical event log ({events.length})</summary><ol className="timeline">{events.map((event) => <li key={event.event_id}><span>{new Date(event.timestamp).toLocaleTimeString()}</span><div><strong>{event.event_type.replaceAll("_", " ")}</strong><pre>{JSON.stringify(event.payload)}</pre></div></li>)}</ol></details>
  </section>;
}
