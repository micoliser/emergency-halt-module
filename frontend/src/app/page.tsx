"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api";
import { Card } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const STEPS = [
  "Connect MetaMask and switch to Studionet.",
  "Open the Demo Vault (or register a protocol if you are setting one up).",
  "Deposit, then withdraw once while the protocol is active.",
  "Report an exploit with the required bond and a public evidence link.",
  "When validators agree, the protocol halts and withdrawals freeze.",
  "The owner lifts the halt with proof the issue is fixed — withdrawals work again.",
];

export default function HomePage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <p className="text-xs uppercase tracking-[0.2em] text-accent">
          Emergency Halt Module
        </p>
        <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Anyone can prove an active exploit. Validators decide. The vault freezes.
        </h1>
        <p className="max-w-2xl text-muted">
          An opt-in safety switch for autonomous protocols. Bonded public reports are
          judged on-chain; if there is an active exploit, linked apps pause withdrawals
          until the owner lifts the halt.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/vault"
            className="rounded-sm bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:brightness-110"
          >
            Open Demo Vault
          </Link>
          <Link
            href="/protocols"
            className="rounded-sm border border-line px-4 py-2 text-sm hover:bg-bg-card"
          >
            Browse protocols
          </Link>
          <Link
            href="/protocols/register"
            className="rounded-sm px-4 py-2 text-sm text-muted hover:text-ink"
          >
            Register a protocol
          </Link>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            How the demo works
          </h2>
          <ol className="space-y-2 text-sm">
            {STEPS.map((step, i) => (
              <li key={step} className="flex gap-3">
                <span className="text-accent">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            Service status
          </h2>
          {health.isLoading && <p className="text-sm text-muted">Checking…</p>}
          {health.error && (
            <p className="text-sm text-halted">
              Cannot reach the app backend. Make sure it is running, then refresh.
            </p>
          )}
          {health.data && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted">Backend</dt>
              <dd>
                <StatusBadge status={health.data.status === "ok" ? "ACTIVE" : "HALTED"} />
              </dd>
              <dt className="text-muted">Protocols</dt>
              <dd>{health.data.indexed.protocols ?? "—"}</dd>
              <dt className="text-muted">Incidents</dt>
              <dd>{health.data.indexed.cases ?? "—"}</dd>
            </dl>
          )}
        </Card>
      </div>
    </div>
  );
}
