export type View = "new" | "live" | "review" | "preview" | "audit";
export interface WorkflowStatus { batch_id: string; thread_id: string; status: string; applied_mappings: Record<string, string>; open_escalations: number; }
export interface WorkflowEvent { event_id: number; batch_id: string; timestamp: string; level: string; event_type: string; payload: Record<string, unknown>; }
export interface Escalation { escalation_id: string; source_context: { kind?: string; record_id?: string; source_file?: string; source_record_id?: string; source_column?: string; field?: string; current_value?: unknown; errors?: string[]; samples?: unknown[]; explanation?: string; conflicting_values?: Record<string, unknown[]> }; suggestion: string | null; alternatives: string[]; confidence_evidence: Record<string, number>; reason_code: string; allowed_actions: string[]; status: string; }
export interface RecordPreview { record_id: string; source_record_id: string; source_file: string; original: Record<string, unknown>; transformed: Record<string, unknown>; status: string; errors: string[]; provenance: Array<{ field: string; rule: string; reason: string }>; }
export interface PushResult { target_write_id: string; source_record_id: string; status: string; retry_count: number; }
export interface ModelRuntimeStatus { mode: string; provider: string; model: string | null; status: string; parallel_workers: number; failover_provider: string | null; failover_status: string; }
export type ExecutionMode = "AUTOPILOT" | "HUMAN_IN_LOOP";
export interface PipelineStage { stage_id: string; agent: string; title: string; description: string; status: string; detail: string; }
export interface PipelineStatus { batch_id: string; execution_mode: ExecutionMode; status: string; current_stage: string; stages: PipelineStage[]; requires_action: boolean; action_message: string; }
