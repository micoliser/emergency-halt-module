import { StatusBadge } from "@/components/StatusBadge";
import { formatGen, formatTimestamp, shortAddress } from "@/lib/format";
import type { CaseEvent } from "@/lib/types";

const EVENT_LABEL: Record<string, string> = {
  REPORT_EVALUATED: "Report evaluated",
  CHALLENGE_EVALUATED: "Challenge evaluated",
  UNHALT_EVALUATED: "Unhalt evaluated",
  APPEAL_FINALIZED: "Appeal finalized",
};

function consensusVerb(eventType: string): string {
  if (eventType === "REPORT_EVALUATED") return "Exploit";
  if (eventType === "CHALLENGE_EVALUATED") return "Overturn";
  if (eventType === "UNHALT_EVALUATED") return "Remediated";
  return "Consensus";
}

function EvidenceLinks({ urls }: { urls: string[] }) {
  if (!urls.length) return null;
  return (
    <ul className="space-y-1">
      {urls.map((url) => (
        <li key={url}>
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="break-all text-xs text-accent hover:underline"
          >
            {url}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function CaseTimeline({ events }: { events: CaseEvent[] }) {
  if (!events.length) {
    return (
      <p className="text-sm text-muted">
        No incident events indexed yet. Refresh after the last transaction confirms.
      </p>
    );
  }

  return (
    <ol className="relative space-y-0 border-l border-accent/40 pl-8">
      {events.map((event) => (
        <li key={event.id} className="relative pb-8 last:pb-0">
          <span className="absolute -left-8 top-1.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-accent ring-4 ring-bg" />
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold">
                {EVENT_LABEL[event.event_type] || event.event_type}
              </p>
              {event.from_status && event.to_status && (
                <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                  <StatusBadge status={event.from_status} />
                  <span>→</span>
                  <StatusBadge status={event.to_status} />
                </span>
              )}
            </div>
            <p className="text-xs text-muted">
              {shortAddress(event.actor, 6)} · {formatTimestamp(event.created_at)}
            </p>
            {event.statement && (
              <p className="whitespace-pre-wrap text-sm">{event.statement}</p>
            )}
            <EvidenceLinks urls={event.evidence_urls ?? []} />
            {event.event_type !== "APPEAL_FINALIZED" && event.consensus_bool != null && (
              <p className="text-sm">
                {consensusVerb(event.event_type)}:{" "}
                <span className="font-medium">
                  {event.consensus_bool ? "yes" : "no"}
                </span>
              </p>
            )}
            {event.consensus_summary && (
              <p className="whitespace-pre-wrap text-sm text-muted">
                {event.consensus_summary}
              </p>
            )}
            {event.bond_disposition && (
              <p className="font-mono text-xs text-muted">
                Bond {formatGen(event.bond_amount)} GEN · {event.bond_disposition}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
