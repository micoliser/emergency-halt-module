import { createReadClient, VIEW_METHODS } from "@/lib/genlayer/client";
import { publicEnv } from "@/lib/env";
import type { VaultConfig } from "@/lib/types";

function asBigInt(value: unknown): bigint {
  if (typeof value === "bigint") return value;
  if (typeof value === "number") return BigInt(value);
  if (typeof value === "string" && value.trim()) return BigInt(value);
  return BigInt(0);
}

function asNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "string") return Number(value);
  return 0;
}

export async function readHaltView<T>(
  functionName: string,
  args: unknown[] = [],
): Promise<T> {
  if (!publicEnv.haltModuleAddress) {
    throw new Error("NEXT_PUBLIC_HALT_MODULE_ADDRESS is not set.");
  }
  const client = createReadClient();
  return (await client.readContract({
    address: publicEnv.haltModuleAddress as `0x${string}`,
    functionName,
    args: args as never,
  })) as T;
}

export async function readVaultView<T>(
  functionName: string,
  args: unknown[] = [],
): Promise<T> {
  if (!publicEnv.demoVaultAddress) {
    throw new Error("NEXT_PUBLIC_DEMO_VAULT_ADDRESS is not set.");
  }
  const client = createReadClient();
  return (await client.readContract({
    address: publicEnv.demoVaultAddress as `0x${string}`,
    functionName,
    args: args as never,
  })) as T;
}

export async function readProtocolCount(): Promise<number> {
  const result = await readHaltView<unknown>(VIEW_METHODS.getProtocolCount, []);
  return asNumber(result);
}

export async function readIsActionAllowed(
  protocolId: number,
  action: string,
): Promise<boolean> {
  const result = await readHaltView<unknown>(VIEW_METHODS.isActionAllowed, [
    protocolId,
    action,
  ]);
  return Boolean(result);
}

export async function readVaultBalance(address: string): Promise<bigint> {
  const result = await readVaultView<unknown>(VIEW_METHODS.getBalance, [address]);
  return asBigInt(result);
}

export async function readVaultConfig(): Promise<VaultConfig> {
  const result = await readVaultView<Record<string, unknown>>(VIEW_METHODS.getConfig, []);
  return {
    halt_module: String(result?.halt_module ?? ""),
    protocol_id: asNumber(result?.protocol_id),
  };
}
