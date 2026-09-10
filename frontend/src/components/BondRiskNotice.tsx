type BondAction = "report" | "challenge" | "unhalt";

const TITLES: Record<BondAction, string> = {
  report: "Stake, risks, and rewards — read before you report",
  challenge: "Stake, risks, and rewards — read before you challenge",
  unhalt: "Stake, risks, and rewards — read before you lift the halt",
};

function scenarios(action: BondAction, stakeLabel: string) {
  if (action === "report") {
    return [
      {
        label: "If validators agree there is an active exploit",
        detail: `The protocol halts. Your ${stakeLabel} is held in escrow (not spent yet). That escrow is returned to you when the window ends without a successful false-alarm challenge, or when the halt is cleared via a real fix.`,
        tone: "good" as const,
      },
      {
        label: "Extra reward if your report was right",
        detail: `You can earn another ${stakeLabel} on top of getting your escrow back when: a challenge fails, someone challenges with a fix (not a false alarm), or the owner/backup successfully lifts the halt. In those cases their stake is paid to you as a reward.`,
        tone: "good" as const,
      },
      {
        label: "If validators disagree (no active exploit)",
        detail: `You lose your ${stakeLabel}. It is paid to the protocol owner. You get no reward.`,
        tone: "bad" as const,
      },
      {
        label: "If someone later proves the halt was a false alarm",
        detail: `You lose your escrowed ${stakeLabel}. It is paid to that challenger as their reward.`,
        tone: "bad" as const,
      },
    ];
  }

  if (action === "challenge") {
    return [
      {
        label: "Use this only for a false alarm",
        detail:
          "Challenge means: the original halt was wrong — there was never a real exploit. If you are proving a fix, the owner/backup should use Lift halt instead.",
        tone: "warn" as const,
      },
      {
        label: "Reward if validators say false alarm",
        detail: `The halt is overturned. You get your ${stakeLabel} back, plus you receive the reporter’s escrowed ${stakeLabel} as a reward (you walk away with about twice what you put in).`,
        tone: "good" as const,
      },
      {
        label: "If validators say the exploit was real but is now fixed",
        detail: `The protocol becomes active again, but you get no reward — you lose your ${stakeLabel}, and it is paid to the original reporter. Posting a fix via challenge still costs you; use Lift halt if you are the owner/backup.`,
        tone: "bad" as const,
      },
      {
        label: "If validators say the exploit is still active",
        detail: `The halt stands. You lose your ${stakeLabel} — it is paid to the reporter as their reward. You get nothing back.`,
        tone: "bad" as const,
      },
    ];
  }

  return [
    {
      label: "This path is for remediation",
      detail:
        "Lift halt means: the original report was real, and the issue is fixed now. Only the owner or a named backup can do this.",
      tone: "warn" as const,
    },
    {
      label: "If validators agree it is fixed",
      detail: `The protocol becomes active again. Your ${stakeLabel} is paid to the original reporter as their reward (you do not get it back). Their escrowed bond is also returned to them.`,
      tone: "good" as const,
    },
    {
      label: "If validators disagree",
      detail: `Your ${stakeLabel} is permanently burned (destroyed). The protocol stays halted. You do not get the funds back, and the reporter is not paid from this attempt.`,
      tone: "bad" as const,
    },
  ];
}

const toneClass = {
  good: "text-active",
  bad: "text-halted",
  warn: "text-ink",
} as const;

export function BondRiskNotice({
  action,
  bondGen,
}: {
  action: BondAction;
  bondGen?: string | null;
}) {
  const stakeLabel =
    bondGen && bondGen.trim() ? `${bondGen.trim()} GEN` : "your stake (B)";
  const items = scenarios(action, stakeLabel);

  return (
    <aside
      className="rounded-sm border border-halted/35 bg-halted/10 px-4 py-3"
      role="note"
      aria-label={TITLES[action]}
    >
      <p className="text-sm font-semibold text-halted">{TITLES[action]}</p>
      <p className="mt-1 text-xs text-muted">
        You must send exactly {stakeLabel} with this transaction. Possible rewards and
        losses depend on what validators decide from public evidence pages.
      </p>
      <ul className="mt-3 space-y-2.5">
        {items.map((item) => (
          <li key={item.label} className="text-sm">
            <p className={`font-medium ${toneClass[item.tone]}`}>{item.label}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.detail}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
