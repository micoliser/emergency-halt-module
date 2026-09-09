"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export function CodeBlock({
  code,
  title,
  className,
}: {
  code: string;
  title?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const text = code.replace(/^\n/, "").replace(/\n$/, "");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className={cn("overflow-hidden rounded-sm border border-line bg-bg", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-1.5">
        <span className="font-mono text-xs text-muted">{title || "code"}</span>
        <button
          type="button"
          onClick={copy}
          className="text-xs text-muted hover:text-ink"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed">
        <code className="font-mono text-ink">{text}</code>
      </pre>
    </div>
  );
}
