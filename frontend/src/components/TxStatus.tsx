import type { TxPhase } from "@/hooks/useTransaction";
import { explorerTxUrl } from "@/lib/format";
import { cn } from "@/lib/utils";

const LABELS: Record<TxPhase, string> = {
  IDLE: "",
  CONFIRMING: "Confirm in MetaMask…",
  SUBMITTED: "Waiting for confirmation…",
  SYNCING: "Updating status…",
  CONFIRMED: "Confirmed",
  FAILED: "Failed",
  UNDETERMINED: "Outcome unclear — refresh to check",
};

export function TxStatus({
  phase,
  error,
  txHash,
  reviewing,
}: {
  phase: TxPhase;
  error?: string | null;
  txHash?: string | null;
  reviewing?: boolean;
}) {
  if (phase === "IDLE" && !error) return null;

  const busy = phase === "CONFIRMING" || phase === "SUBMITTED" || phase === "SYNCING";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "rounded-sm border px-3 py-2 text-sm",
        phase === "FAILED" && "border-halted/40 bg-halted/10 text-halted",
        phase === "CONFIRMED" && "border-active/40 bg-active/10 text-active",
        phase === "UNDETERMINED" && "border-warn/40 bg-warn/10 text-warn",
        busy && "border-warn/40 bg-warn/10 text-warn",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p>
          {busy && (
            <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-warn" />
          )}
          {reviewing && phase === "SUBMITTED"
            ? "Validators are reviewing evidence… this can take 30–60s."
            : LABELS[phase] || error}
        </p>
        {txHash && (
          <a
            className="font-mono text-xs underline decoration-line underline-offset-2 hover:text-ink"
            href={explorerTxUrl(txHash)}
            target="_blank"
            rel="noreferrer"
          >
            {txHash.slice(0, 10)}…
          </a>
        )}
      </div>
      {error && phase === "FAILED" && <p className="mt-1 text-xs opacity-90">{error}</p>}
    </div>
  );
}
