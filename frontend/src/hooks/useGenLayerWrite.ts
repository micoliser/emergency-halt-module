"use client";

import { useCallback, useState } from "react";
import { useAccount } from "wagmi";
import { createWriteClient } from "@/lib/genlayer/client";
import { ensureStudionetChain } from "@/lib/genlayer/chain";
import {
  asOnchainId,
  extractExecutionError,
  extractWriteReturn,
  humanizeTxError,
} from "@/lib/receipt";

/** genlayer-js TransactionStatus numeric codes (do not treat 3/4 as terminal). */
const STATUS_BY_CODE: Record<string, string> = {
  "0": "UNINITIALIZED",
  "1": "PENDING",
  "2": "PROPOSING",
  "3": "COMMITTING",
  "4": "REVEALING",
  "5": "ACCEPTED",
  "6": "UNDETERMINED",
  "7": "FINALIZED",
  "8": "CANCELED",
  "9": "APPEAL_REVEALING",
  "10": "APPEAL_COMMITTING",
  "11": "READY_TO_FINALIZE",
  "12": "VALIDATORS_TIMEOUT",
  "13": "LEADER_TIMEOUT",
};

const EXEC_BY_CODE: Record<string, string> = {
  "0": "NOT_VOTED",
  "1": "FINISHED_WITH_RETURN",
  "2": "FINISHED_WITH_ERROR",
};

const SUCCESS_STATUS = new Set(["ACCEPTED", "FINALIZED"]);
const FAILED_STATUS = new Set([
  "UNDETERMINED",
  "CANCELED",
  "VALIDATORS_TIMEOUT",
  "LEADER_TIMEOUT",
  "REVERTED",
  "ERROR",
]);

const POLL_MS = 3000;
const MAX_POLLS = 40; // ~2 minutes fail-closed

type Receipt = Record<string, unknown> & {
  txExecutionResultName?: string;
  hash?: string;
};

function normalizeStatus(tx: Record<string, unknown>): string {
  const named = tx.statusName ?? tx.status_name;
  if (typeof named === "string" && named.trim()) {
    const upper = named.trim().toUpperCase().replace(/\s+/g, "_");
    return STATUS_BY_CODE[upper] ?? upper;
  }
  const raw = String(tx.status ?? tx.txStatus ?? "").toUpperCase();
  return STATUS_BY_CODE[raw] ?? raw;
}

function normalizeExec(tx: Record<string, unknown>): string {
  const named = tx.txExecutionResultName;
  if (typeof named === "string" && named.trim()) {
    return named.trim().toUpperCase().replace(/\s+/g, "_");
  }
  const raw = String(tx.txExecutionResult ?? "");
  return EXEC_BY_CODE[raw] ?? raw.toUpperCase();
}

function isExplicitExecutionError(tx: Record<string, unknown>, exec: string): boolean {
  if (exec === "FINISHED_WITH_ERROR") return true;
  // Narrow signals only — do not scan for generic "message" fields.
  const detail = extractExecutionError(tx);
  return Boolean(detail);
}

async function waitForReceipt(
  // genlayer-js client is loosely typed across CJS/ESM builds
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  client: any,
  txHash: string,
): Promise<Receipt> {
  let lastError: unknown;
  let consecutiveFetchFailures = 0;

  for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
    try {
      const tx = (await client.getTransaction({ hash: txHash })) as Record<string, unknown> | null;
      consecutiveFetchFailures = 0;
      if (tx) {
        const status = normalizeStatus(tx);
        const exec = normalizeExec(tx);

        if (FAILED_STATUS.has(status) || exec === "FINISHED_WITH_ERROR") {
          tx.txExecutionResultName = "FINISHED_WITH_ERROR";
          return tx as Receipt;
        }

        if (SUCCESS_STATUS.has(status)) {
          // Resolve as soon as the tx is accepted/finalized so the UI can sync.
          // Error scanning must not throw (bigint JSON) or we keep polling forever.
          try {
            if (isExplicitExecutionError(tx, exec)) {
              tx.txExecutionResultName = "FINISHED_WITH_ERROR";
              return tx as Receipt;
            }
          } catch (scanErr) {
            console.warn("Could not scan receipt for execution errors:", scanErr);
          }
          tx.txExecutionResultName = "FINISHED_WITH_RETURN";
          return tx as Receipt;
        }
      }
    } catch (err) {
      lastError = err;
      consecutiveFetchFailures += 1;
      const msg = err instanceof Error ? err.message.toLowerCase() : String(err).toLowerCase();
      if (msg.includes("429") || msg.includes("rate limit")) {
        await sleep(POLL_MS * 2);
        continue;
      }
      // Browser RPC flakes should not spin forever after the chain already settled.
      if (
        consecutiveFetchFailures >= 5 &&
        (msg.includes("failed to fetch") || msg.includes("network") || msg.includes("fetch"))
      ) {
        throw new Error(
          "Could not confirm the transaction from this browser. Refresh the page to see the latest status.",
        );
      }
    }
    await sleep(POLL_MS);
  }
  const extra = lastError instanceof Error ? ` Last error: ${lastError.message}` : "";
  throw new Error(`Timed out waiting for transaction confirmation.${extra}`);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useGenLayerWrite() {
  const { address, isConnected } = useAccount();
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitTransaction = useCallback(
    async (
      contractAddress: string,
      functionName: string,
      args: unknown[],
      onTxHash?: (hash: string) => void,
      value?: bigint,
    ) => {
      if (!isConnected || !address) {
        throw new Error("Connect MetaMask first.");
      }
      if (!contractAddress) {
        throw new Error("Contract address is not configured.");
      }

      setIsPending(true);
      setError(null);
      try {
        await ensureStudionetChain();
        const client = createWriteClient(address as `0x${string}`);
        try {
          await client.connect("studionet");
        } catch (err) {
          console.warn(
            "genlayer-js connect() failed (snap/chain); continuing with injected provider:",
            err,
          );
        }

        const txHash = (await client.writeContract({
          address: contractAddress as `0x${string}`,
          functionName,
          args: args as never,
          value: value ?? BigInt(0),
        })) as string;

        onTxHash?.(txHash);

        const receipt = await waitForReceipt(client, txHash);

        if (receipt.txExecutionResultName === "FINISHED_WITH_ERROR") {
          const detail = extractExecutionError(receipt);
          throw new Error(
            detail ||
              "This action was rejected on-chain. Your balance was not changed.",
          );
        }

        const returned = extractWriteReturn(receipt);
        const returnedId = asOnchainId(returned);

        return { txHash, receipt, returned, returnedId };
      } catch (err) {
        const message = humanizeTxError(err);
        setError(message);
        throw new Error(message);
      } finally {
        setIsPending(false);
      }
    },
    [address, isConnected],
  );

  return { submitTransaction, isPending, error };
}
