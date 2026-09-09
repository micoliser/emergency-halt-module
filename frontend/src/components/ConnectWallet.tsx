"use client";

import { useState } from "react";
import { useAccount, useConnect, useDisconnect } from "wagmi";
import { injected } from "wagmi/connectors/injected";
import { useHasMounted } from "@/hooks/useHasMounted";
import { ensureStudionetChain, studionetChain } from "@/lib/genlayer/chain";
import { requireMetaMaskProvider } from "@/lib/genlayer/client";
import { shortAddress } from "@/lib/format";

export function ConnectWallet() {
  const mounted = useHasMounted();
  const { address, isConnected, chainId } = useAccount();
  const { connectAsync } = useConnect();
  const { disconnectAsync } = useDisconnect();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onConnect = async () => {
    setError("");
    setBusy(true);
    try {
      requireMetaMaskProvider();
      if (!isConnected) {
        await connectAsync({ connector: injected({ target: "metaMask" }) });
      }
      await ensureStudionetChain();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect wallet.");
    } finally {
      setBusy(false);
    }
  };

  const onDisconnect = async () => {
    setError("");
    await disconnectAsync();
  };

  if (!mounted) {
    return (
      <div className="h-9 w-36 animate-pulse rounded-sm bg-line/60" aria-hidden />
    );
  }

  if (isConnected && address) {
    const wrongChain = chainId != null && chainId !== studionetChain.id;
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="flex items-center gap-2">
          {wrongChain && (
            <button
              type="button"
              onClick={() => ensureStudionetChain()}
              className="rounded-sm border border-warn/40 bg-warn/10 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-warn"
            >
              Switch to studionet
            </button>
          )}
          <span className="rounded-sm border border-line bg-bg-card px-2.5 py-1 font-mono text-xs text-ink">
            {shortAddress(address, 4)}
          </span>
          <button
            type="button"
            onClick={onDisconnect}
            className="text-xs text-muted hover:text-ink"
          >
            Disconnect
          </button>
        </div>
        {error && <p className="max-w-xs text-right text-xs text-halted">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onConnect}
        disabled={busy}
        className="rounded-sm bg-accent px-3 py-1.5 text-sm font-semibold text-accent-ink hover:brightness-110 disabled:opacity-50"
      >
        {busy ? "Connecting…" : "Connect MetaMask"}
      </button>
      {error && <p className="max-w-xs text-right text-xs text-halted">{error}</p>}
    </div>
  );
}
