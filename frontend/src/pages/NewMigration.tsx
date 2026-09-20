import { useRef, useState } from "react";
import { api } from "../api/client";
import type { ExecutionMode } from "../types";

const fields = ["employee_id", "first_name", "last_name", "email", "phone", "date_of_birth", "hire_date", "department", "employment_status", "manager_id", "source_system"];

export function NewMigration({ onCreated }: { onCreated: (batchId: string) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("AUTOPILOT");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function choose(selected: File[]) {
    if (selected.length > 10 || selected.some((file) => file.size > 10 * 1024 * 1024 || file.size === 0)) {
      setError("Choose up to 10 non-empty files, each no larger than 10 MB.");
      setFiles([]);
      return;
    }
    const invalid = selected.find((file) => !/\.(csv|xlsx)$/i.test(file.name));
    setError(invalid ? `${invalid.name} is not supported. Choose a CSV (.csv) or Excel (.xlsx) file.` : "");
    setFiles(invalid ? [] : selected);
  }

  async function submit() {
    setBusy(true);
    setError("");
    try {
      onCreated((await api.upload(files, executionMode)).batch_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return <section aria-labelledby="new-title">
    <div className="section-heading"><div><p className="eyebrow">Step 1 of 5</p><h2 id="new-title">Upload employee files</h2></div><p>Choose how the agents should work, then add one or more source exports.</p></div>
    <fieldset className="mode-picker"><legend>How should this migration run?</legend>
      <label className={executionMode === "AUTOPILOT" ? "selected" : ""}><input type="radio" name="execution-mode" checked={executionMode === "AUTOPILOT"} onChange={() => setExecutionMode("AUTOPILOT")} /><span><strong>Autopilot</strong><small>Starting authorizes automatic matching, cleanup and sending valid records to the demo destination. We ask only about uncertain data. You can undo sent records in Results.</small></span></label>
      <label className={executionMode === "HUMAN_IN_LOOP" ? "selected" : ""}><input type="radio" name="execution-mode" checked={executionMode === "HUMAN_IN_LOOP"} onChange={() => setExecutionMode("HUMAN_IN_LOOP")} /><span><strong>Human-in-the-loop</strong><small>Keep the original supervised flow: analyze mappings, review uncertainty, preview validated data, then choose whether to push.</small></span></label>
    </fieldset>
    <ol className="workflow-guide" aria-label="Migration steps"><li className="current"><b>1</b><span><strong>Upload agent</strong><small>CSV or Excel</small></span></li><li><b>2</b><span><strong>Analyze agent</strong><small>Generate mappings</small></span></li><li><b>3</b><span><strong>Review agent</strong><small>Apply policy</small></span></li><li><b>4</b><span><strong>Validation agent</strong><small>Clean and validate</small></span></li><li><b>5</b><span><strong>Integration agent</strong><small>Send valid employees</small></span></li></ol>
    <div className="format-notice"><strong>Supported input files</strong><span>CSV <code>.csv</code> and Excel <code>.xlsx</code>. Up to 10 files, 10 MB each. Upload employee exports together to combine duplicates. Excel uses the first worksheet.</span></div>
    <div className="split"><div className="panel">
      <button className="dropzone" type="button" onClick={() => input.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); choose([...event.dataTransfer.files]); }}><span className="drop-icon">↑</span><strong>Drop CSV or Excel files here</strong><span>Accepted: .csv and .xlsx</span><span>or choose files from your computer</span></button>
      <input ref={input} className="sr-only" aria-label="Choose employee files" type="file" multiple accept=".csv,.xlsx" onChange={(event) => choose([...(event.target.files ?? [])])} />
      {files.length > 0 && <><p className="selection-summary"><strong>{files.length} file{files.length === 1 ? "" : "s"} selected</strong><span>Next: the upload agent profiles the files and opens the agent pipeline.</span></p><ul className="file-list" aria-label="Selected files">{files.map((file) => <li key={file.name}><span>{file.name}</span><small>{(file.size / 1024).toFixed(1)} KB</small></li>)}</ul></>}
      {error && <p role="alert" className="error">{error}</p>}
      <button className="primary" disabled={!files.length || busy} onClick={submit}>{busy ? "Upload agent is profiling files…" : `Start ${executionMode === "AUTOPILOT" ? "autopilot" : "guided"} migration${files.length ? ` (${files.length})` : ""}`}</button>
    </div><aside className="panel schema"><p className="eyebrow">Destination fields</p><h3>Employee record</h3><p>Required fields must be present or reviewed before data can be pushed.</p><ul>{fields.map((field, index) => <li key={field}><code>{field}</code>{index < 4 || [6, 7, 8].includes(index) ? <span>Required</span> : <span>Optional</span>}</li>)}</ul></aside></div>
  </section>;
}
