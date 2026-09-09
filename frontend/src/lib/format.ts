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

export function isEthAddress(value: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(value.trim());
}

/** Governor or a named backup may request unhalt. */
export function isUnhaltAuthority(
  wallet?: string | null,
  protocol?: { governor: string; backup_unhalters?: string[] } | null,
): boolean {
  if (!wallet || !protocol) return false;
  if (sameAddress(wallet, protocol.governor)) return true;
  return (protocol.backup_unhalters ?? []).some((addr) => sameAddress(wallet, addr));
}

/** Exact wei for payable report / challenge / unhalt. Do not parseGen this string. */
export function bondWei(reporterBond: string | null | undefined): bigint {
  if (reporterBond == null || reporterBond === "") {
    throw new Error("Could not read the required bond amount.");
  }
  return BigInt(reporterBond);
}

/** End boundary comes from the API; `now` is the client clock for display ticks. */
export function msUntil(iso: string | null | undefined, now = Date.now()): number | null {
  if (!iso) return null;
  const end = new Date(iso).getTime();
  if (Number.isNaN(end)) return null;
  return end - now;
}

export function isAppealWindowOpen(
  appealEndsAt?: string | null,
  now = Date.now(),
): boolean {
  const remaining = msUntil(appealEndsAt, now);
  return remaining != null && remaining > 0;
}

export function formatDuration(ms: number): string {
  if (ms <= 0) return "0s";
  const total = Math.floor(ms / 1000);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const parts: string[] = [];
  if (days) parts.push(`${days}d`);
  if (hours || days) parts.push(`${hours}h`);
  if (minutes || hours || days) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return parts.join(" ");
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
