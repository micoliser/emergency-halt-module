import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { publicEnv, STUDIONET_CHAIN_ID, STUDIONET_RPC_URL } from "@/lib/env";

const fallbackChain = {
  id: STUDIONET_CHAIN_ID,
  isStudio: true,
  name: "Genlayer Studio Network",
  rpcUrls: {
    default: {
      http: [publicEnv.rpcUrl || STUDIONET_RPC_URL],
    },
  },
  nativeCurrency: { name: "GEN Token", symbol: "GEN", decimals: 18 },
};

export function studioChain() {
  return studionet || fallbackChain;
}

export function createReadClient() {
  return createClient({
    chain: studioChain(),
  });
}

export function requireMetaMaskProvider() {
  if (typeof window === "undefined") {
    throw new Error("Wallet is only available in the browser.");
  }
  const provider = window.ethereum;
  if (!provider) {
    throw new Error("No wallet found. Install MetaMask.");
  }
  if (!provider.isMetaMask) {
    throw new Error("Only MetaMask is supported. Switch to MetaMask and retry.");
  }
  return provider;
}

export function createWriteClient(account: `0x${string}`) {
  const provider = requireMetaMaskProvider();
  return createClient({
    chain: studioChain(),
    account,
    provider,
  });
}

export const WRITE_METHODS = {
  registerProtocol: "register_protocol",
  reportExploit: "report_exploit",
  requestUnhalt: "request_unhalt",
  deposit: "deposit",
  withdraw: "withdraw",
} as const;

export const VIEW_METHODS = {
  getProtocolCount: "get_protocol_count",
  getProtocol: "get_protocol",
  isActionAllowed: "is_action_allowed",
  getBalance: "get_balance",
  getConfig: "get_config",
} as const;
