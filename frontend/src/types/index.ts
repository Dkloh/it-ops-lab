export interface Service {
  id: number;
  name: string;
  environment: string;
  description: string | null;
  created_at: string;
}
export interface Batch {
  id: number;
  service_id: number;
  filename: string;
  status: string;
  accepted_count: number;
  rejected_count: number;
  created_at: string;
}
export interface IngestionError {
  line_number: number;
  reason: string;
}
export interface Event {
  id: number;
  service_id: number;
  batch_id: number;
  occurred_at: string;
  severity: string;
  message: string;
  source: string | null;
  metadata: Record<string, unknown> | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Summary {
  total: number;
  by_severity: Record<string, number>;
  by_service: {
    service_id: number;
    name: string;
    environment: string;
    count: number;
  }[];
  earliest: string | null;
  latest: string | null;
}
export interface Evidence {
  id: number;
  occurred_at: string;
  severity: string;
  source: string | null;
  message: string;
}
export interface Finding {
  id: number;
  run_id: number;
  rule_code: string;
  severity: string;
  summary: string;
  explanation: string;
  suggested_action: string;
  first_seen_at: string;
  last_seen_at: string;
  event_count: number;
  event_ids: number[];
}
export interface FindingDetail extends Finding {
  service_id: number;
  batch_id: number;
  evidence: Evidence[];
}
export interface RunItem {
  id: number;
  batch_id: number;
  ruleset_version: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  finding_count: number;
}
export interface Run extends RunItem {
  service_id: number;
  findings: Finding[];
}
export type CheckType = "DNS" | "TCP" | "HTTP";
export interface TargetInput {
  name: string;
  check_type: CheckType;
  host: string;
  enabled: boolean;
  port?: number;
  scheme?: "http" | "https";
  path?: string;
}
export interface Target {
  id: number;
  service_id: number;
  name: string;
  check_type: CheckType;
  host: string;
  port: number | null;
  scheme: string | null;
  path: string | null;
  enabled: boolean;
  created_at: string;
}
export interface Result {
  id: number;
  target_id: number;
  outcome: "success" | "failure";
  duration_ms: number;
  error_code: string | null;
  status_code: number | null;
  details_json: Record<string, unknown>;
  checked_at: string;
}
export interface Overview {
  service_count: number;
  event_count: number;
  error_count: number;
  warning_count: number;
  latest_findings: (Pick<
    Finding,
    "id" | "run_id" | "rule_code" | "severity" | "summary" | "last_seen_at"
  > & { service_id: number; recorded_at: string })[];
  recent_observations: (Result & { target_name: string; service_id: number })[];
}
