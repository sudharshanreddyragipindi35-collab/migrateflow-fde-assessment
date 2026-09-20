import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { PushResult } from "../types";
import { StatusPill } from "../components/StatusPill";

export function IntegrationAudit({ batchId }: { batchId: string }) {
  const [rows, setRows] = useState<PushResult[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (batchId) api.pushes(batchId).then(setRows).catch((reason: Error) => setError(reason.message));
  }, [batchId]);
  const sent = rows.filter((row) => row.status === "SUCCESS").length;
  const failed = rows.filter((row) => row.status.endsWith("FAILURE")).length;
  const undone = rows.some((row) => row.status === "ROLLED_BACK");
  const retryable = !undone && rows.some((row) => row.status === "RETRYABLE_FAILURE" && row.retry_count < 3);
  async function act(action: "retry" | "rollback") {
    if (action === "rollback" && !window.confirm("Undo records sent by this migration? Other migrations will not change.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      if (action === "retry") {
        const results = await api.retry(batchId);
        setRows(results);
        const remaining = results.filter((row) => row.status.endsWith("FAILURE")).length;
        setMessage(remaining ? `${remaining} record(s) still need attention.` : "All approved records were sent successfully.");
      } else {
        const result = await api.rollback(batchId);
        setMessage(`${result.rolled_back} sent record(s) undone. Start a new migration to send again.`);
        setRows(await api.pushes(batchId));
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The action could not be completed. Please retry."); }
    finally { setBusy(false); }
  }
  return <section>
    <div className="section-heading"><div><p className="eyebrow">Migration results</p><h2>Integration audit</h2><p>See what reached the demo destination. Retry temporary failures or undo this migration.</p></div>
      <div className="actions"><button onClick={() => void act("retry")} disabled={busy || !retryable}>Retry failed records</button><button className="danger" onClick={() => void act("rollback")} disabled={busy || !sent}>Undo sent records</button></div></div>
    {!!rows.length && <p role="status">{sent} sent · {failed} failed · {rows.filter((row) => row.status === "ROLLED_BACK").length} undone</p>}
    {busy && <p role="status">Saving results…</p>}
    {message && <p role="status" className="success">{message}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="table-wrap"><table><thead><tr><th>Source row</th><th>Result</th><th>Retries</th><th>What happens next</th></tr></thead><tbody>{rows.map((row) => <tr key={row.target_write_id}><td>{row.source_record_id}</td><td><StatusPill value={row.status} /></td><td>{row.retry_count} / 3</td><td>{row.status === "PERMANENT_FAILURE" ? "Check the source data and start a corrected migration." : row.status === "RETRYABLE_FAILURE" ? "Temporary destination error. Use Retry failed records." : row.status === "ROLLED_BACK" ? "Undone. No further action needed." : "Sent successfully. No action needed."}</td></tr>)}</tbody></table>
      {!rows.length && <div className="empty"><h3>No records sent yet</h3><p>Complete any required review. Autopilot sends valid employees automatically; guided mode waits for your decision.</p></div>}
    </div>
  </section>;
}
