import { formatUnits, parseUnits } from "viem";

const GEN_DECIMALS = 18;

/** Format a u256 decimal string (or bigint) as a trimmed GEN display value. */
export function formatGen(
  wei: string | bigint | number | null | undefined,
  maxFractionDigits = 6,
): string {
  if (wei === undefined || wei === null || wei === "") return "0";
  try {
    const raw = formatUnits(BigInt(wei), GEN_DECIMALS);
    const [whole, frac = ""] = raw.split(".");
    if (!frac || maxFractionDigits === 0) return whole;
    const trimmed = frac.slice(0, maxFractionDigits).replace(/0+$/, "");
    return trimmed ? `${whole}.${trimmed}` : whole;
  } catch {
    return String(wei);
  }
}

/** Parse a human GEN amount into a wei bigint for payable writes. */
export function parseGen(amount: string): bigint {
  const cleaned = amount.trim();
  if (!cleaned) throw new Error("Amount is required");
  return parseUnits(cleaned, GEN_DECIMALS);
}

export function shortAddress(address: string | null | undefined, chars = 4): string {
  if (!address) return "—";
  if (address.length < chars * 2 + 2) return address;
  return `${address.slice(0, 2 + chars)}…${address.slice(-chars)}`;
}

export function sameAddress(a?: string | null, b?: string | null): boolean {
  if (!a || !b) return false;
  return a.toLowerCase() === b.toLowerCase();
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function csvToList(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function explorerTxUrl(hash: string): string {
  return `https://explorer-studio.genlayer.com/tx/${hash}`;
}
