import { publicEnv } from "@/lib/env";
import {
  ApiError,
  type Case,
  type CaseDetail,
  type HealthResponse,
  type Paginated,
  type Protocol,
  type ProtocolDetail,
  type SyncProtocolResponse,
} from "@/lib/types";

function apiBase(): string {
  return publicEnv.apiUrl.replace(/\/$/, "");
}

function withSlash(path: string): string {
  const [pathname, query] = path.split("?", 2);
  const normalized = pathname.endsWith("/") ? pathname : `${pathname}/`;
  return query ? `${normalized}?${query}` : normalized;
}

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail != null) return JSON.stringify(body.detail);
  } catch {
    /* ignore */
  }
  return res.statusText || `Request failed (${res.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${apiBase()}${withSlash(path)}`;
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface ListParams {
  offset?: number;
  limit?: number;
  status?: string;
  governor?: string;
  protocol_id?: number;
  reporter?: string;
}

function query(params?: ListParams): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  if (params.offset != null) sp.set("offset", String(params.offset));
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.status) sp.set("status", params.status);
  if (params.governor) sp.set("governor", params.governor);
  if (params.protocol_id != null) sp.set("protocol_id", String(params.protocol_id));
  if (params.reporter) sp.set("reporter", params.reporter);
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function getProtocols(params?: ListParams): Promise<Paginated<Protocol>> {
  return request<Paginated<Protocol>>(`/api/protocols${query(params)}`);
}

export function getProtocol(id: number): Promise<ProtocolDetail> {
  return request<ProtocolDetail>(`/api/protocols/${id}`);
}

export function getProtocolCases(
  protocolId: number,
  params?: ListParams,
): Promise<Paginated<Case>> {
  return request<Paginated<Case>>(`/api/protocols/${protocolId}/cases${query(params)}`);
}

export function getCases(params?: ListParams): Promise<Paginated<Case>> {
  return request<Paginated<Case>>(`/api/cases${query(params)}`);
}

export function getCase(id: number): Promise<CaseDetail> {
  return request<CaseDetail>(`/api/cases/${id}`);
}

/** Custom header so classic form CSRF cannot forge sync POSTs (forces preflight). */
const SYNC_CSRF_HEADER = { "X-Requested-With": "ProofHalt" } as const;

/**
 * Fast-path resync after a wallet write. Goes through the Next.js proxy so
 * X-Sync-Secret never ships in NEXT_PUBLIC_* env.
 */
export async function syncProtocol(id: number): Promise<SyncProtocolResponse> {
  const res = await fetch(`/api/sync/protocols/${id}`, {
    method: "POST",
    headers: SYNC_CSRF_HEADER,
    signal: AbortSignal.timeout(45_000),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  return (await res.json()) as SyncProtocolResponse;
}

export async function syncAll(): Promise<{ synced: unknown }> {
  const res = await fetch("/api/sync/all", {
    method: "POST",
    headers: SYNC_CSRF_HEADER,
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  return (await res.json()) as { synced: unknown };
}
