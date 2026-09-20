import { useEffect, useState } from "react";
import { api } from "./api/client";
import { DataPreview } from "./pages/DataPreview";
import { IntegrationAudit } from "./pages/IntegrationAudit";
import { LiveRun } from "./pages/LiveRun";
import { NewMigration } from "./pages/NewMigration";
import { ReviewQueue } from "./pages/ReviewQueue";
import type { ModelRuntimeStatus, View } from "./types";

const navigation: Array<[View, string, string]> = [
  ["new", "1", "Upload files"], ["live", "2", "Analyze and map"], ["review", "3", "Review decisions"],
  ["preview", "4", "Preview data"], ["audit", "5", "Push and audit"],
];

export function App() {
  const [view, setView] = useState<View>(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    return navigation.some(([id]) => id === requested) ? requested as View : "new";
  });
  const [batchId, setBatchId] = useState(() => new URLSearchParams(window.location.search).get("batch") ?? window.localStorage.getItem("migrateflow.batchId") ?? "");
  const [modelRuntime, setModelRuntime] = useState<ModelRuntimeStatus | null>(null);
  useEffect(() => {
    api.modelStatus().then(setModelRuntime).catch(() => setModelRuntime(null));
  }, []);
  function activateBatch(id: string) {
    setBatchId(id);
    window.localStorage.setItem("migrateflow.batchId", id);
    window.history.replaceState(null, "", `?batch=${encodeURIComponent(id)}&view=live`);
  }
  function showView(next: View) {
    setView(next);
    const params = new URLSearchParams(window.location.search);
    params.set("view", next);
    window.history.replaceState(null, "", `?${params.toString()}`);
  }
  const content = {
    new: <NewMigration onCreated={(id) => { activateBatch(id); showView("live"); }} />,
    live: <LiveRun batchId={batchId} onReview={() => showView("review")} onPreview={() => showView("preview")} onAudit={() => showView("audit")} />,
    review: <ReviewQueue batchId={batchId} onCompleted={() => showView("live")} onPreview={() => showView("preview")} />,
    preview: <DataPreview batchId={batchId} onPushed={() => showView("audit")} />,
    audit: <IntegrationAudit batchId={batchId} />,
  }[view];
  return <div className="shell"><aside className="sidebar"><a className="brand" href="#main" aria-label="MigrateFlow home"><span>M</span><strong>MigrateFlow</strong></a><nav aria-label="Primary navigation">{navigation.map(([id, icon, label]) => <button key={id} className={view === id ? "active" : ""} aria-current={view === id ? "page" : undefined} onClick={() => showView(id)}><span>{icon}</span>{label}{id === "review" && <b>!</b>}</button>)}</nav><div className="sidebar-foot"><span className="secure-dot" />Secure model path<p>PII-safe context</p></div></aside><main id="main"><header><div><span className="secure-dot" /> Supervised mode{modelRuntime && <> · {modelRuntime.provider}{modelRuntime.model ? ` / ${modelRuntime.model}` : ""} · {modelRuntime.mode === "fallback" ? "no LLM workers" : `${modelRuntime.parallel_workers} parallel workers`} · {modelRuntime.status}{modelRuntime.failover_provider ? ` · failover: ${modelRuntime.failover_provider} ${modelRuntime.failover_status}` : ""}</>}</div>{batchId ? <code>{batchId.slice(0, 8)}</code> : <span>No active batch</span>}</header><div className="content">{content}</div></main></div>;
}
