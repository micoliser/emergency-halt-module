export type ProtocolStatus = "ACTIVE" | "HALTED" | string;
export type CaseStatus =
  | "OPEN"
  | "ACCEPTED_HALT"
  | "REJECTED"
  | "OVERTURNED"
  | "CLEARED"
  | string;

export type CaseEventType =
  | "REPORT_EVALUATED"
  | "CHALLENGE_EVALUATED"
  | "UNHALT_EVALUATED"
  | "APPEAL_FINALIZED"
  | string;

export interface Protocol {
  id: number;
  name: string;
  status: ProtocolStatus;
  is_halted: boolean;
  governor: string;
  /** 0–3 checksum addresses that may request unhalt. */
  backup_unhalters: string[];
  exploit_definition: string;
  trusted_domains: string[];
  protected_actions: string[];
  allowed_while_halted: string[];
  min_evidence: number;
  appeal_window_seconds: number;
  /** Decimal string (u256). Do not parse as Number. */
  reporter_bond: string;
  reporter_bond_gen: string;
  /** 0 means no active case. */
  active_case_id: number;
  case_count: number;
  /** ISO-8601 UTC, or null when not halted. */
  halted_at: string | null;
  /** ISO-8601 UTC = halted_at + appeal window, or null when not halted. */
  appeal_ends_at: string | null;
  created_at: string | null;
  synced_at: string | null;
}

export interface CaseEvent {
  id: number;
  case_id: number;
  protocol_id: number;
  event_type: CaseEventType;
  actor: string;
  statement: string;
  evidence_urls: string[];
  consensus_bool: boolean | null;
  consensus_summary: string;
  from_status: string;
  to_status: string;
  /** Decimal wei string (u256). */
  bond_amount: string;
  bond_disposition: string;
  created_at: string | null;
}

export interface Case {
  id: number;
  protocol_id: number;
  reporter: string;
  allegation: string;
  evidence_urls: string[];
  verdict_exploit: boolean | null;
  verdict_summary: string;
  status: CaseStatus;
  /** Decimal string (u256). */
  bond_amount: string;
  bond_amount_gen: string;
  bond_settled: boolean;
  /** Append-only event count (list shape). */
  event_count?: number;
  submitted_at: string | null;
  synced_at: string | null;
}

export interface ProtocolDetail extends Protocol {
  active_case: Case | null;
}

export interface CaseDetail extends Case {
  protocol: {
    id: number;
    name: string;
    status: ProtocolStatus;
    governor: string;
  };
  /** Oldest-first incident timeline. */
  events: CaseEvent[];
}

export interface Paginated<T> {
  count: number;
  offset: number;
  limit: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface HealthResponse {
  status: string;
  database: { ok: boolean; error: string };
  chain: {
    rpc_url: string;
    chain_id: number;
    halt_module_address: string;
    demo_vault_address: string;
    configured: boolean;
  };
  indexed: {
    protocols: number | null;
    cases: number | null;
    events?: number | null;
  };
  cursor: {
    protocol_count: number;
    case_count: number;
    case_event_count?: number;
    last_success_at: string | null;
    last_error: string;
  } | null;
}

export interface SyncProtocolResponse {
  synced: Record<string, unknown>;
  protocol: ProtocolDetail | null;
}

export interface VaultConfig {
  halt_module: string;
  protocol_id: number;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}
