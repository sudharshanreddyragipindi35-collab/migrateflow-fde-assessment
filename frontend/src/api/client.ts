import type { Escalation, ExecutionMode, ModelRuntimeStatus, PipelineStatus, PushResult, RecordPreview, WorkflowStatus } from "../types";
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
async function request<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(`${baseUrl}${path}`, init); if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body?.error?.message ?? `Request failed with ${response.status}`); } return response.json() as Promise<T>; }
export const api = {
  modelStatus: () => request<ModelRuntimeStatus>("/api/system/model"),
  upload(files: File[], executionMode: ExecutionMode) { const body = new FormData(); files.forEach((file) => body.append("files", file)); body.append("execution_mode", executionMode); return request<{ batch_id: string }>("/api/batches", { method: "POST", body }); },
  pipeline: (batchId: string) => request<PipelineStatus>(`/api/batches/${batchId}/pipeline`),
  advancePipeline: (batchId: string) => request<PipelineStatus>(`/api/batches/${batchId}/pipeline/run`, { method: "POST" }),
  decidePush: (batchId: string, decision: "PUSH" | "DO_NOT_PUSH") => request<PipelineStatus>(`/api/batches/${batchId}/pipeline/push-decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) }),
  cancelPipeline: (batchId: string) => request<PipelineStatus>(`/api/batches/${batchId}/pipeline/cancel`, { method: "POST" }),
  propose: (batchId: string) => request(`/api/batches/${batchId}/mapping-proposals`, { method: "POST" }),
  start: (batchId: string) => request<WorkflowStatus>(`/api/batches/${batchId}/workflow/start`, { method: "POST" }),
  status: (batchId: string) => request<WorkflowStatus>(`/api/batches/${batchId}/workflow/status`),
  transform: (batchId: string) => request<RecordPreview[]>(`/api/batches/${batchId}/records/transform`, { method: "POST" }),
  escalations: (batchId: string) => request<Escalation[]>(`/api/batches/${batchId}/escalations`),
  resolve(id: string, action: string, correctedValue?: string) { return request<WorkflowStatus>(`/api/escalations/${id}/resolve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, corrected_value: correctedValue, actor: "consultant" }) }); },
  records: (batchId: string) => request<RecordPreview[]>(`/api/batches/${batchId}/records`),
  pushValid: (batchId: string) => request<PushResult[]>(`/mock-target/migrations/${batchId}/push-valid`, { method: "POST" }),
  pushes: (batchId: string) => request<PushResult[]>(`/mock-target/migrations/${batchId}`),
  retry: (batchId: string) => request<PushResult[]>(`/mock-target/migrations/${batchId}/retry`, { method: "POST" }),
  rollback: (batchId: string) => request<{ rolled_back: number }>(`/mock-target/migrations/${batchId}`, { method: "DELETE" }),
  eventUrl: (batchId: string) => `${baseUrl}/api/batches/${batchId}/events`,
};
