"use client";

import { contractsConfigured, vaultConfigured } from "@/lib/env";

export function ConfigBanner() {
  const haltOk = contractsConfigured();
  const vaultOk = vaultConfigured();
  if (haltOk && vaultOk) return null;

  return (
    <div className="border-b border-warn/30 bg-warn/10 px-4 py-2 text-sm text-warn">
      <p>
        {!haltOk
          ? "This demo is not fully configured yet. Contract setup is still missing — ask the deployer to finish environment setup."
          : "The Demo Vault address is not configured yet. Protocol pages work; the vault page will stay limited until it is set."}
      </p>
    </div>
  );
}
