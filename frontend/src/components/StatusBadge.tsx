import { cn } from "@/lib/utils";

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const upper = (status || "").toUpperCase();
  const tone =
    upper === "ACTIVE" || upper === "CLEARED" || upper === "OVERTURNED"
      ? "border-active/40 bg-active/15 text-active"
      : upper === "HALTED" || upper === "ACCEPTED_HALT"
        ? "border-halted/40 bg-halted/15 text-halted"
        : upper === "REJECTED"
          ? "border-line bg-bg-elev text-muted"
          : "border-warn/40 bg-warn/15 text-warn";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider",
        tone,
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          upper === "HALTED" || upper === "ACCEPTED_HALT"
            ? "animate-pulse bg-halted"
            : upper === "ACTIVE" || upper === "CLEARED" || upper === "OVERTURNED"
              ? "bg-active"
              : "bg-warn",
        )}
      />
      {upper || "UNKNOWN"}
    </span>
  );
}
