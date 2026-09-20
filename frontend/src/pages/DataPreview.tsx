import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ExecutionMode, RecordPreview } from "../types";
import { StatusPill } from "../components/StatusPill";

export function DataPreview({ batchId, onPushed }: { batchId: string; onPushed: () => void }) {
  const [records, setRecords] = useState<RecordPreview[]>([]);
  const [filter, setFilter] = useState("ALL");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("HUMAN_IN_LOOP");
  useEffect(() => { if (batchId) api.records(batchId).then(setRecords).catch(() => setRecords([])); }, [batchId]);
  useEffect(() => { if (batchId) api.pipeline(batchId).then((result) => setExecutionMode(result.execution_mode)).catch(() => undefined); }, [batchId]);
  const visible = filter === "ALL" ? records : records.filter((record) => record.status === filter);
  const validCount = records.filter((record) => record.status === "VALID").length;
  const pendingCount = records.filter((record) => record.status === "ESCALATION").length;
  const label = (value: string) => value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());

  async function decide(decision: "PUSH" | "DO_NOT_PUSH") {
    setBusy(true);
    setError("");
    try {
      if (executionMode === "HUMAN_IN_LOOP") {
        if (decision === "PUSH") await api.pushValid(batchId);
      } else {
        await api.decidePush(batchId, decision);
      }
      onPushed();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The final decision could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return <section>
    <div className="section-heading"><div><p className="eyebrow">Traceable changes</p><h2>Data preview</h2><p>{executionMode === "AUTOPILOT" ? "Autopilot sends valid records after all required reviews are resolved. View Results to check delivery or undo sent records." : "Check the cleaned records, then choose Send valid records. Unresolved reviews block sending."}</p></div><div className="actions"><label>Filter <select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="ALL">All records</option><option value="VALID">Ready</option><option value="ESCALATION">Needs review</option><option value="REJECTED">Excluded</option></select></label>{executionMode === "AUTOPILOT" ? <button onClick={onPushed}>View results</button> : <button className="primary" disabled={!validCount || !!pendingCount || busy} onClick={() => void decide("PUSH")}>{busy ? "Sending records…" : `Send valid records (${validCount})`}</button>}</div></div>
    {error && <p role="alert" className="error">{error}</p>}
    <p>{validCount} ready · {pendingCount} need review · {records.filter((record) => record.status === "REJECTED").length} excluded</p>
    <div className="table-wrap"><table><thead><tr><th>Status</th><th>Source</th><th>Employee details</th><th>What changed and why</th></tr></thead><tbody>{visible.map((record) => <tr key={record.record_id}><td><StatusPill value={record.status} /></td><td>{record.source_file} · row {record.source_record_id}</td><td><dl>{Object.entries(record.transformed).map(([field, value]) => <div key={field}><dt><strong>{label(field)}</strong></dt><dd>{String(value ?? "Not provided")}</dd></div>)}</dl></td><td><ul>{record.provenance.map((item, index) => <li key={index}>{label(item.field)}: {item.reason}</li>)}</ul>{record.errors.map((error) => <p className="error" key={error}>{error}</p>)}<details><summary>View original source values</summary><pre>{JSON.stringify(record.original, null, 2)}</pre></details></td></tr>)}</tbody></table>{!visible.length && <div className="empty"><h3>No preview records</h3><p>Complete mapping and required reviews first. Validated transformations will then appear here.</p></div>}</div>
  </section>;
}
