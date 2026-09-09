"""Cached mirror of Halt Module cases (bonded reports + AI verdicts)."""

from django.db import models

from apps.protocols.models import Protocol


class CaseStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ACCEPTED_HALT = "ACCEPTED_HALT", "Accepted (halt)"
    REJECTED = "REJECTED", "Rejected"
    OVERTURNED = "OVERTURNED", "Overturned"
    CLEARED = "CLEARED", "Cleared"


class Case(models.Model):
    # Case IDs are 1-indexed on-chain so `active_case_id == 0` means "none".
    onchain_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name="cases"
    )
    protocol_onchain_id = models.PositiveBigIntegerField(db_index=True)

    reporter = models.CharField(max_length=42, db_index=True)
    allegation = models.TextField(blank=True)
    evidence_urls = models.JSONField(default=list, blank=True)

    verdict_exploit = models.BooleanField(default=False)
    verdict_summary = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=CaseStatus.choices, db_index=True)

    # u256 — decimal string (see Protocol.reporter_bond).
    bond_amount = models.CharField(max_length=80, default="0")
    bond_settled = models.BooleanField(default=False)
    chain_submitted_at = models.DateTimeField(null=True, blank=True)

    raw = models.JSONField(default=dict, blank=True)

    synced_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-onchain_id"]
        verbose_name = "case"
        verbose_name_plural = "cases"

    def __str__(self) -> str:
        return f"case #{self.onchain_id} protocol #{self.protocol_onchain_id} ({self.status})"
