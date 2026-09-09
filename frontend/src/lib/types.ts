export type ProtocolStatus = "ACTIVE" | "HALTED" | string;
export type CaseStatus =
  | "OPEN"
  | "ACCEPTED_HALT"
  | "REJECTED"
  | "OVERTURNED"
  | "CLEARED"
  | string;

export interface Protocol {
  id: number;
  name: string;
  status: ProtocolStatus;
  is_halted: boolean;
  governor: string;
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
  created_at: string | null;
  synced_at: string | null;
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
  indexed: { protocols: number | null; cases: number | null };
  cursor: {
    protocol_count: number;
    case_count: number;
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
