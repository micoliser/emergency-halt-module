import Link from "next/link";
import { cn } from "@/lib/utils";

type ProofHaltLogoProps = {
  className?: string;
  /** Show wordmark next to the mark (navbar). */
  withWordmark?: boolean;
  /** Pixel size of the mark. */
  size?: number;
  href?: string | null;
};

export function ProofHaltLogo({
  className,
  withWordmark = false,
  size = 32,
  href = "/",
}: ProofHaltLogoProps) {
  const mark = (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      {/* Native img: local SVG avoids next/image SVG restrictions */}
      <img
        src="/logo.svg"
        alt=""
        width={size}
        height={size}
        className="shrink-0 rounded-[22%]"
        decoding="async"
      />
      {withWordmark && (
        <span className="flex flex-col leading-none">
          <span className="text-base font-semibold tracking-tight text-ink">
            ProofHalt
          </span>
          <span className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-muted">
            proof · then freeze
          </span>
        </span>
      )}
      <span className="sr-only">ProofHalt</span>
    </span>
  );

  if (href == null) return mark;
  return (
    <Link href={href} className="inline-flex items-center hover:opacity-90">
      {mark}
    </Link>
  );
}
