"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui";
import { getCase } from "@/lib/api";
import { formatTimestamp, shortAddress } from "@/lib/format";
import { ApiError } from "@/lib/types";

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const invalid = !Number.isInteger(id) || id < 1;

  const q = useQuery({
    queryKey: ["case", id],
    queryFn: () => getCase(id),
    enabled: !invalid,
  });

  if (invalid) {
    return <p className="text-halted">Invalid incident.</p>;
  }
  if (q.isLoading) return <p className="text-muted">Loading incident…</p>;
  if (q.error) {
    const err = q.error;
    return (
      <p className="text-halted">
        {err instanceof ApiError && err.status === 404
          ? "This incident is not available yet. Refresh the protocol page and try again."
          : err instanceof Error
            ? err.message
            : "Failed to load incident."}
      </p>
    );
  }
  const c = q.data;
  if (!c) return null;

  const exploitLabel =
    c.verdict_exploit === true
      ? "Validators agreed there was an active exploit"
      : c.verdict_exploit === false
        ? "Validators did not find an active exploit"
        : "No verdict yet";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <p className="text-sm">
        <Link href={`/protocols/${c.protocol_id}`} className="text-muted hover:text-ink">
          ← {c.protocol?.name || "Back to protocol"}
        </Link>
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Incident report</h1>
        <StatusBadge status={c.status} />
        {c.protocol && <StatusBadge status={c.protocol.status} />}
      </div>

      <Card className="space-y-4 text-sm">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Allegation
          </h2>
          <p className="mt-1 whitespace-pre-wrap">{c.allegation}</p>
        </div>
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Decision
          </h2>
          <p className="mt-1">{exploitLabel}</p>
          <p className="mt-2 whitespace-pre-wrap text-muted">
            {c.verdict_summary || "—"}
          </p>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
          <dt className="text-muted">Reporter</dt>
          <dd>{shortAddress(c.reporter, 6)}</dd>
          <dt className="text-muted">Bond</dt>
          <dd>
            {c.bond_amount_gen} GEN
            {c.bond_settled ? " (settled)" : " (pending)"}
          </dd>
          <dt className="text-muted">Submitted</dt>
          <dd>{formatTimestamp(c.submitted_at)}</dd>
        </dl>
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Evidence
          </h2>
          <ul className="mt-1 space-y-1">
            {c.evidence_urls.map((url) => (
              <li key={url}>
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="break-all text-xs text-accent hover:underline"
                >
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </Card>
    </div>
  );
}
