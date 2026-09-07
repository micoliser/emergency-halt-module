# Demo script (60–90s)

> Stub — fill in after M5 frontend cold path works.

1. Connect MetaMask to Studionet (chain id 61999).
2. Register a protocol (trusted domain = demo evidence host).
3. Deposit into Demo Vault; withdraw once while ACTIVE.
4. Submit bonded report with exploit evidence URL → status HALTED.
5. Withdraw fails (`is_action_allowed` false).
6. Governor unhalt with remediation URL → ACTIVE; withdraw works again.
