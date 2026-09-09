"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAccount } from "wagmi";
import { AppealCountdown } from "@/components/AppealCountdown";
import { StatusBadge } from "@/components/StatusBadge";
import { TxStatus } from "@/components/TxStatus";
import { Card, GhostButton, PrimaryButton } from "@/components/ui";
import { useHasMounted } from "@/hooks/useHasMounted";
import { useNow } from "@/hooks/useNow";
import { useTransaction } from "@/hooks/useTransaction";
import { getProtocol, getProtocolCases, syncProtocol } from "@/lib/api";
import { contractsConfigured, publicEnv } from "@/lib/env";
import {
  formatTimestamp,
  isAppealWindowOpen,
  isUnhaltAuthority,
  shortAddress,
} from "@/lib/format";
import { WRITE_METHODS } from "@/lib/genlayer/client";
import { ApiError } from "@/lib/types";
import { useState } from "react";

function humanActionList(actions: string[]): string {
  if (!actions.length) return "none";
  return actions
    .map((a) => {
      if (a === "withdraw") return "withdraw money";
      if (a === "transfer") return "transfer funds";
      if (a === "deposit") return "deposit";
      return a;
    })
    .join(", ");
}

export default function ProtocolDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const invalid = !Number.isInteger(id) || id < 0;
  const mounted = useHasMounted();
  const { address } = useAccount();
  const qc = useQueryClient();
  const { execute, txPhase, isLocked, error, txHash } = useTransaction();
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  const protocolQ = useQuery({
    queryKey: ["protocol", id],
    queryFn: () => getProtocol(id),
    enabled: !invalid,
  });
  const casesQ = useQuery({
    queryKey: ["protocol-cases", id],
    queryFn: () => getProtocolCases(id, { limit: 50 }),
    enabled: !invalid,
  });

  const p = protocolQ.data;
  const backups = p?.backup_unhalters ?? [];
  const isAuthority = isUnhaltAuthority(address, p);
  const halted = p?.status === "HALTED" || Boolean(p?.is_halted);
  const now = useNow(halted);
  const activeCase = p?.active_case ?? null;
  const windowOpen = now != null && isAppealWindowOpen(p?.appeal_ends_at, now);
  const windowClosed =
    now != null && p?.appeal_ends_at != null && !isAppealWindowOpen(p.appeal_ends_at, now);
  const canChallenge =
    halted && activeCase?.status === "ACCEPTED_HALT" && windowOpen;
  const canFinalize =
    halted &&
    activeCase?.status === "ACCEPTED_HALT" &&
    windowClosed &&
    activeCase.bond_settled === false;

  const onSync = async () => {
    setSyncError(null);
    setSyncing(true);
    try {
      const res = await syncProtocol(id);
      if (res.protocol) {
        qc.setQueryData(["protocol", id], res.protocol);
      }
      await qc.invalidateQueries({ queryKey: ["protocol-cases", id] });
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Could not refresh.");
    } finally {
      setSyncing(false);
    }
  };

  const onFinalize = async () => {
    setFinalizeError(null);
    if (!p) return;
    if (!contractsConfigured()) {
      setFinalizeError("Contracts are not configured yet.");
      return;
    }
    await execute(
      publicEnv.haltModuleAddress,
      WRITE_METHODS.finalizeAppeal,
      [p.id],
      {
        confirmingMessage: "Confirm finalize in MetaMask…",
        submittedMessage: "Finalize submitted…",
        confirmedMessage: "Escrow released to the reporter. Protocol stays halted until an authority unhalts.",
        syncProtocolId: p.id,
        onConfirmed: async ({ protocol }) => {
          if (protocol) qc.setQueryData(["protocol", p.id], protocol);
          await qc.invalidateQueries({ queryKey: ["protocol-cases", p.id] });
          if (p.active_case_id) {
            await qc.invalidateQueries({ queryKey: ["case", p.active_case_id] });
          }
        },
      },
    );
  };

  if (invalid) {
    return <p className="text-halted">Invalid protocol.</p>;
  }
  if (protocolQ.isLoading) {
    return <p className="text-muted">Loading protocol…</p>;
  }
  if (protocolQ.error) {
    const err = protocolQ.error;
    const notFound = err instanceof ApiError && err.status === 404;
    return (
      <Card className="space-y-3">
        <p className="text-halted">
          {notFound
            ? `This protocol is not available yet. Try refreshing.`
            : err instanceof Error
              ? err.message
              : "Failed to load protocol."}
        </p>
        <GhostButton onClick={onSync} disabled={syncing}>
          {syncing ? "Refreshing…" : "Refresh status"}
        </GhostButton>
        {syncError && <p className="text-xs text-halted">{syncError}</p>}
      </Card>
    );
  }
  if (!p) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">{p.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={p.status} />
            {p.active_case_id === 0 ? (
              <span className="text-xs text-muted">No open incident</span>
            ) : (
              <Link
                href={`/cases/${p.active_case_id}`}
                className="text-xs text-accent hover:underline"
              >
                Open incident #{p.active_case_id}
              </Link>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <GhostButton onClick={onSync} disabled={syncing}>
            {syncing ? "Refreshing…" : "Refresh status"}
          </GhostButton>
          {p.status === "ACTIVE" && (
            <Link
              href={`/protocols/${p.id}/report`}
              className="rounded-sm bg-halted px-4 py-2 text-sm font-semibold text-white"
            >
              Report exploit
            </Link>
          )}
          {canChallenge && p.active_case_id > 0 && (
            <Link
              href={`/cases/${p.active_case_id}#challenge`}
              className="rounded-sm border border-line px-4 py-2 text-sm font-semibold hover:bg-bg-card"
            >
              Challenge halt
            </Link>
          )}
          {halted && isAuthority && (
            <Link
              href={`/protocols/${p.id}/unhalt`}
              className="rounded-sm bg-accent px-4 py-2 text-sm font-semibold text-accent-ink"
            >
              Lift halt
            </Link>
          )}
          {canFinalize && (
            <PrimaryButton
              type="button"
              onClick={onFinalize}
              disabled={!mounted || isLocked}
            >
              {isLocked ? "Working…" : "Release escrow"}
            </PrimaryButton>
          )}
          {halted && mounted && address && !isAuthority && (
            <p className="self-center text-xs text-muted">
              Only the owner or a named backup can lift the halt.
            </p>
          )}
        </div>
      </div>

      {syncError && <p className="text-sm text-halted">{syncError}</p>}
      {(txPhase !== "IDLE" || finalizeError) && (
        <TxStatus phase={txPhase} error={error || finalizeError} txHash={txHash} />
      )}

      {halted && (
        <Card className="border-halted/40 space-y-3">
          <p className="text-sm">
            This protocol is <strong>halted</strong>. Linked apps like the Demo Vault
            will not let people withdraw until the owner or a backup lifts the halt
            with proof that the issue is fixed.
          </p>
          <AppealCountdown appealEndsAt={p.appeal_ends_at} />
          {canChallenge && (
            <p className="text-sm text-muted">
              Anyone can challenge this halt with stake {p.reporter_bond_gen} GEN
              while the window is open.
            </p>
          )}
          {canFinalize && (
            <p className="text-sm text-muted">
              The challenge window is closed. Releasing escrow returns the reporter’s
              bond without unhalting.
            </p>
          )}
          <p className="text-sm text-muted">
            Deposits into the Demo Vault can still work during a halt — only taking money
            out is frozen.
          </p>
          <div className="flex flex-wrap gap-3">
            {p.active_case_id > 0 && (
              <Link
                href={`/cases/${p.active_case_id}`}
                className="text-sm text-accent hover:underline"
              >
                Open incident timeline →
              </Link>
            )}
            <Link href="/vault" className="text-sm text-accent hover:underline">
              Open Demo Vault →
            </Link>
          </div>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3 text-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Safety rules
          </h2>
          <p className="whitespace-pre-wrap">{p.exploit_definition}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
            <dt className="text-muted">Owner</dt>
            <dd className="truncate text-xs" title={p.governor}>
              {shortAddress(p.governor, 6)}
            </dd>
            <dt className="text-muted">Backup unhalters</dt>
            <dd className="text-xs">
              {backups.length === 0
                ? "None"
                : backups.map((addr) => (
                    <span key={addr} className="block truncate" title={addr}>
                      {shortAddress(addr, 6)}
                    </span>
                  ))}
            </dd>
            <dt className="text-muted">Stake B</dt>
            <dd>{p.reporter_bond_gen} GEN (report, challenge, unhalt)</dd>
            <dt className="text-muted">Evidence links needed</dt>
            <dd>{p.min_evidence}</dd>
            <dt className="text-muted">Trusted websites</dt>
            <dd>{p.trusted_domains.join(", ") || "—"}</dd>
            <dt className="text-muted">Actions frozen when halted</dt>
            <dd>{humanActionList(p.protected_actions)}</dd>
            <dt className="text-muted">Exceptions while halted</dt>
            <dd>
              {p.allowed_while_halted.length
                ? humanActionList(p.allowed_while_halted)
                : "None — frozen actions stay blocked"}
            </dd>
          </dl>
          <p className="text-xs text-muted">
            “Exceptions while halted” only applies to the frozen actions above. The Demo
            Vault does not freeze deposits, so you can still add funds during a halt.
          </p>
        </Card>
        <Card className="space-y-3 text-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Status
          </h2>
          <p>
            {halted
              ? "Paused after a confirmed exploit report."
              : "Running normally. Reports can pause protected actions."}
          </p>
          {p.halted_at && (
            <p className="text-xs text-muted">
              Halted at {formatTimestamp(p.halted_at)}
            </p>
          )}
          <p className="text-xs text-muted">
            Last updated {formatTimestamp(p.synced_at)}
          </p>
        </Card>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Incident history</h2>
        {casesQ.isLoading && <p className="text-sm text-muted">Loading…</p>}
        {(casesQ.data?.results.length ?? 0) === 0 && !casesQ.isLoading && (
          <p className="text-sm text-muted">No reports yet.</p>
        )}
        <div className="space-y-2">
          {(casesQ.data?.results ?? []).map((c) => (
            <Link
              key={c.id}
              href={`/cases/${c.id}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-line bg-bg-card px-4 py-3 hover:border-accent/50"
            >
              <div>
                <p className="text-sm">{c.allegation}</p>
                <p className="text-xs text-muted">
                  Reported by {shortAddress(c.reporter)} · bond {c.bond_amount_gen} GEN
                  {c.event_count != null ? ` · ${c.event_count} event${c.event_count === 1 ? "" : "s"}` : ""}
                </p>
              </div>
              <StatusBadge status={c.status} />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
