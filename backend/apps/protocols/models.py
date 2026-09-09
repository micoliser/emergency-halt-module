"""
Cached mirror of Halt Module protocols.

Nothing here is authoritative: every field is a copy of an on-chain view
result. `raw` keeps the untouched snapshot so a shape change on-chain is
recoverable without a migration.
"""

from django.db import models


class ProtocolStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    HALTED = "HALTED", "Halted"


class Protocol(models.Model):
    onchain_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=16, choices=ProtocolStatus.choices, db_index=True
    )
    governor = models.CharField(max_length=42, db_index=True)
    exploit_definition = models.TextField(blank=True)

    # trusted_domains / protected_actions / allowed_while_halted /
    # min_evidence / appeal_window_seconds
    config = models.JSONField(default=dict, blank=True)

    # u256 — decimal string so JS clients never lose precision.
    reporter_bond = models.CharField(max_length=80, default="0")

    active_case_id = models.PositiveBigIntegerField(default=0)
    onchain_case_count = models.PositiveIntegerField(default=0)
    chain_created_at = models.DateTimeField(null=True, blank=True)

    raw = models.JSONField(default=dict, blank=True)

    synced_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["onchain_id"]
        verbose_name = "protocol"
        verbose_name_plural = "protocols"

    def __str__(self) -> str:
        return f"#{self.onchain_id} {self.name} ({self.status})"

    @property
    def is_halted(self) -> bool:
        return self.status == ProtocolStatus.HALTED

    def config_list(self, key: str) -> list[str]:
        value = (self.config or {}).get(key) or []
        return [str(item) for item in value]
