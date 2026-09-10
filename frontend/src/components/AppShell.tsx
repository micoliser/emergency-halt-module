"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ConfigBanner } from "@/components/ConfigBanner";
import { ConnectWallet } from "@/components/ConnectWallet";
import { ProofHaltLogo } from "@/components/ProofHaltLogo";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/protocols", label: "Protocols" },
  { href: "/protocols/register", label: "Register" },
  { href: "/vault", label: "Demo Vault" },
  { href: "/guide", label: "Guide" },
];

function navActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/protocols") {
    return pathname === "/protocols" || /^\/protocols\/\d/.test(pathname);
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line bg-bg-elev/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <ProofHaltLogo withWordmark size={36} />
            <nav className="hidden items-center gap-1 md:flex">
              {NAV.map((item) => {
                const active = navActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-sm px-2.5 py-1 text-sm",
                      active
                        ? "bg-bg-card text-ink"
                        : "text-muted hover:bg-bg-card hover:text-ink",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <ConnectWallet />
        </div>
        <nav className="flex gap-1 overflow-x-auto border-t border-line px-4 py-2 md:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="shrink-0 rounded-sm px-2 py-1 text-xs text-muted hover:text-ink"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <ConfigBanner />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      <footer className="border-t border-line px-4 py-4 text-center text-xs text-muted">
        <span className="inline-flex items-center justify-center gap-2">
          <ProofHaltLogo href={null} size={18} />
          ProofHalt · GenLayer Studionet demo
        </span>
      </footer>
    </div>
  );
}
