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
    event_count = models.PositiveIntegerField(default=0)
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


class CaseEventType(models.TextChoices):
    REPORT_EVALUATED = "REPORT_EVALUATED", "Report evaluated"
    CHALLENGE_EVALUATED = "CHALLENGE_EVALUATED", "Challenge evaluated"
    UNHALT_EVALUATED = "UNHALT_EVALUATED", "Unhalt evaluated"
    APPEAL_FINALIZED = "APPEAL_FINALIZED", "Appeal finalized"


class CaseEvent(models.Model):
    """
    Append-only mirror of Halt Module case events.

    Historical payloads are never rewritten: a re-sync of the same
    `onchain_id` is an idempotent no-op when the snapshot matches.
    """

    onchain_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    protocol_onchain_id = models.PositiveBigIntegerField(db_index=True)

    event_type = models.CharField(
        max_length=32, choices=CaseEventType.choices, db_index=True
    )
    actor = models.CharField(max_length=42, db_index=True)
    statement = models.TextField(blank=True)
    evidence_urls = models.JSONField(default=list, blank=True)

    consensus_bool = models.BooleanField(default=False)
    consensus_summary = models.TextField(blank=True)
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, blank=True)

    # u256 — decimal string (see Protocol.reporter_bond).
    bond_amount = models.CharField(max_length=80, default="0")
    bond_disposition = models.CharField(max_length=80, blank=True)

    chain_created_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    synced_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["onchain_id"]
        verbose_name = "case event"
        verbose_name_plural = "case events"

    def __str__(self) -> str:
        return f"event #{self.onchain_id} case #{self.case_id} ({self.event_type})"
