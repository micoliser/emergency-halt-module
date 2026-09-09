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

export async function ensureStudionetChain(): Promise<void> {
  const eth = typeof window !== "undefined" ? window.ethereum : undefined;
  if (!eth?.request) return;
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
      return;
    }
    // Studionet RPC is GenLayer JSON-RPC, not always eth_chainId-compatible.
    // Writes still go through genlayer-js client.connect("studionet").
    console.warn("Could not switch MetaMask to studionet:", err);
  }
}
