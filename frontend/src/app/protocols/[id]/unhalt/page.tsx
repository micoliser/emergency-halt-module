"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAccount } from "wagmi";
import { StatusBadge } from "@/components/StatusBadge";
import { TxStatus } from "@/components/TxStatus";
import { Card, Field, PrimaryButton, TextArea } from "@/components/ui";
import { useHasMounted } from "@/hooks/useHasMounted";
import { useTransaction } from "@/hooks/useTransaction";
import { getProtocol } from "@/lib/api";
import { contractsConfigured, publicEnv } from "@/lib/env";
import { csvToList, sameAddress } from "@/lib/format";
import { WRITE_METHODS } from "@/lib/genlayer/client";

export default function UnhaltPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();
  const mounted = useHasMounted();
  const { address, isConnected } = useAccount();
  const { execute, txPhase, isLocked, error, txHash } = useTransaction();
  const protocolQ = useQuery({
    queryKey: ["protocol", id],
    queryFn: () => getProtocol(id),
    enabled: Number.isInteger(id) && id >= 0,
  });

  const [statement, setStatement] = useState("");
  const [urls, setUrls] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const p = protocolQ.data;
  const isGovernor = sameAddress(address, p?.governor);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!p) return;
    if (!contractsConfigured()) {
      setLocalError("Contracts are not configured yet.");
      return;
    }
    if (!isConnected) {
      setLocalError("Connect MetaMask first.");
      return;
    }
    if (!isGovernor) {
      setLocalError("Only the protocol owner can lift the halt.");
      return;
    }
    if (p.status !== "HALTED") {
      setLocalError("You can only lift the halt while the protocol is halted.");
      return;
    }
    const evidence = csvToList(urls.replace(/\n/g, ","));
    if (!statement.trim() || evidence.length === 0) {
      setLocalError("Describe the fix and add at least one evidence link.");
      return;
    }

    await execute(
      publicEnv.haltModuleAddress,
      WRITE_METHODS.requestUnhalt,
      [p.id, statement.trim(), JSON.stringify(evidence)],
      {
        confirmingMessage: "Confirm in MetaMask…",
        submittedMessage: "Request submitted. Waiting for confirmation…",
        reviewingMessage: "Validators are reviewing the remediation evidence…",
        confirmedMessage: "Request finished. The protocol should be active again.",
        syncProtocolId: p.id,
        onConfirmed: async ({ protocol }) => {
          if (protocol) qc.setQueryData(["protocol", p.id], protocol);
          router.push(`/protocols/${p.id}`);
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <p className="text-sm">
        <Link href={`/protocols/${id}`} className="text-muted hover:text-ink">
          ← Back to protocol
        </Link>
      </p>
      <div>
        <h1 className="text-2xl font-semibold">Lift the halt</h1>
        <p className="text-sm text-muted">
          Only the protocol owner can do this. Validators must agree the exploit is fixed
          before the protocol becomes active again.
        </p>
      </div>

      {p && (
        <Card className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-medium">{p.name}</p>
            <p className="text-xs text-muted">
              {isGovernor ? "You are the owner." : "Your wallet is not the owner."}
            </p>
          </div>
          <StatusBadge status={p.status} />
        </Card>
      )}

      <Card>
        <form className="space-y-4" onSubmit={onSubmit}>
          <Field label="What was fixed?">
            <TextArea
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
              placeholder="The vulnerable path has been patched. The exploit is closed."
              maxLength={2000}
              required
            />
          </Field>
          <Field
            label="Proof links"
            hint="Public links on a trusted website for this protocol."
          >
            <TextArea
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
              placeholder="https://rentry.co/your-remediation-page"
              required
            />
          </Field>
          <TxStatus
            phase={txPhase}
            error={error || localError}
            txHash={txHash}
            reviewing
          />
          <PrimaryButton
            type="submit"
            disabled={!mounted || isLocked || !p || p.status !== "HALTED" || !isGovernor}
          >
            {isLocked ? "Working…" : "Request to lift halt"}
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}
