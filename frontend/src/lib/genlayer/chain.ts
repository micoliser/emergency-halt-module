import { defineChain } from "viem";
import { createConfig, http } from "wagmi";
import { injected } from "wagmi/connectors/injected";
import {
  chainIdHex,
  publicEnv,
  STUDIONET_CHAIN_ID,
  STUDIONET_EXPLORER,
  STUDIONET_RPC_URL,
} from "@/lib/env";

export const studionetChain = defineChain({
  id: publicEnv.chainId || STUDIONET_CHAIN_ID,
  name: "GenLayer Studionet",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: {
    default: { http: [publicEnv.rpcUrl || STUDIONET_RPC_URL] },
  },
  blockExplorers: {
    default: { name: "Studio Explorer", url: STUDIONET_EXPLORER },
  },
});

export const wagmiConfig = createConfig({
  chains: [studionetChain],
  connectors: [injected({ target: "metaMask" })],
  transports: {
    [studionetChain.id]: http(publicEnv.rpcUrl || STUDIONET_RPC_URL),
  },
  ssr: true,
});

export const studionetWalletParams = {
  chainId: chainIdHex(studionetChain.id),
  chainName: "GenLayer Studionet",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: [publicEnv.rpcUrl || STUDIONET_RPC_URL],
  blockExplorerUrls: [STUDIONET_EXPLORER],
};

async function readProviderChainId(
  eth: { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> },
): Promise<string> {
  const raw = await eth.request({ method: "eth_chainId" });
  return String(raw ?? "").toLowerCase();
}

/**
 * Switch MetaMask to Studionet and verify eth_chainId matches.
 * Throws (fail closed) if the provider is missing or still on the wrong chain.
 */
export async function ensureStudionetChain(): Promise<void> {
  const eth = typeof window !== "undefined" ? window.ethereum : undefined;
  if (!eth?.request) {
    throw new Error("No Ethereum provider found. Install MetaMask.");
  }

  const expected = studionetWalletParams.chainId.toLowerCase();

  try {
    await eth.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: studionetWalletParams.chainId }],
    });
  } catch (err: unknown) {
    const code = (err as { code?: number }).code;
    if (code === 4902 || code === -32603) {
      await eth.request({
        method: "wallet_addEthereumChain",
        params: [studionetWalletParams],
      });
      // Adding a chain does not always switch to it — switch explicitly.
      await eth.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: studionetWalletParams.chainId }],
      });
    } else {
      throw err instanceof Error
        ? err
        : new Error("Could not switch MetaMask to Studionet.");
    }
  }

  const current = await readProviderChainId(eth);
  if (current !== expected) {
    throw new Error(
      `Wrong network: expected Studionet (${expected}), got ${current || "unknown"}. Switch MetaMask and try again.`,
    );
  }
}
