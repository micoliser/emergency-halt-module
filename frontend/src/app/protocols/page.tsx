"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, GhostButton } from "@/components/ui";
import { getProtocols } from "@/lib/api";
import { shortAddress } from "@/lib/format";

const PAGE = 20;

export default function ProtocolsPage() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const query = useQuery({
    queryKey: ["protocols", offset, status],
    queryFn: () =>
      getProtocols({
        offset,
        limit: PAGE,
        status: status || undefined,
      }),
  });

  const rows = query.data?.results ?? [];
  const count = query.data?.count ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE < count;
  const range = useMemo(() => {
    if (!count) return "0";
    return `${offset + 1}–${Math.min(offset + PAGE, count)} of ${count}`;
  }, [offset, count]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Protocols</h1>
          <p className="text-sm text-muted">
            Registered safety configs. Open one to report an exploit or lift a halt.
          </p>
        </div>
        <Link
          href="/protocols/register"
          className="rounded-sm bg-accent px-4 py-2 text-sm font-semibold text-accent-ink"
        >
          Register
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-muted">
          Status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
            className="ml-2 rounded-sm border border-line bg-bg px-2 py-1 text-ink"
          >
            <option value="">All</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="HALTED">HALTED</option>
          </select>
        </label>
      </div>

      {query.isLoading && <p className="text-sm text-muted">Loading protocols…</p>}
      {query.error && (
        <p className="text-sm text-halted">
          {query.error instanceof Error ? query.error.message : "Failed to load protocols."}
        </p>
      )}

      {!query.isLoading && rows.length === 0 && (
        <Card>
          <p className="text-sm text-muted">
            No protocols yet. Register one to get started.
          </p>
        </Card>
      )}

      <div className="space-y-2">
        {rows.map((p) => (
          <Link
            key={p.id}
            href={`/protocols/${p.id}`}
            className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-line bg-bg-card px-4 py-3 hover:border-accent/50"
          >
            <div>
              <p className="font-medium">{p.name}</p>
              <p className="text-xs text-muted">
                Owner {shortAddress(p.governor)} · report bond {p.reporter_bond_gen} GEN
              </p>
            </div>
            <StatusBadge status={p.status} />
          </Link>
        ))}
      </div>

      {count > PAGE && (
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-xs text-muted">{range}</p>
          <div className="flex gap-2">
            <GhostButton disabled={!canPrev} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Previous
            </GhostButton>
            <GhostButton disabled={!canNext} onClick={() => setOffset(offset + PAGE)}>
              Next
            </GhostButton>
          </div>
        </div>
      )}
    </div>
  );
}
