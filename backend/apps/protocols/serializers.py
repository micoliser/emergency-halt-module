"""
Frontend-ready protocol shapes.

These response shapes are frozen for Phase 5 (IMPLEMENTATION_PLAN.md Phase 4
fallback note): add fields, never rename or remove them.

v1.1 additive fields:
- `backup_unhalters`: checksum-normalized address list (0–3)
- `halted_at`: ISO-8601 UTC datetime, or null when not halted (unix 0 on-chain)
- `appeal_ends_at`: ISO-8601 UTC datetime = halted_at + appeal_window_seconds,
  or null when not halted. Window expiry is a challenge deadline only.
"""

from datetime import timedelta

from rest_framework import serializers

from apps.common.units import format_gen
from apps.protocols.models import Protocol


class ProtocolSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="onchain_id", read_only=True)
    trusted_domains = serializers.SerializerMethodField()
    protected_actions = serializers.SerializerMethodField()
    allowed_while_halted = serializers.SerializerMethodField()
    min_evidence = serializers.SerializerMethodField()
    appeal_window_seconds = serializers.SerializerMethodField()
    reporter_bond_gen = serializers.SerializerMethodField()
    case_count = serializers.IntegerField(source="onchain_case_count", read_only=True)
    created_at = serializers.DateTimeField(source="chain_created_at", read_only=True)
    is_halted = serializers.BooleanField(read_only=True)
    appeal_ends_at = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = [
            "id",
            "name",
            "status",
            "is_halted",
            "governor",
            "backup_unhalters",
            "exploit_definition",
            "trusted_domains",
            "protected_actions",
            "allowed_while_halted",
            "min_evidence",
            "appeal_window_seconds",
            "reporter_bond",
            "reporter_bond_gen",
            "active_case_id",
            "case_count",
            "halted_at",
            "appeal_ends_at",
            "created_at",
            "synced_at",
        ]
        read_only_fields = fields

    def get_trusted_domains(self, obj: Protocol) -> list[str]:
        return obj.config_list("trusted_domains")

    def get_protected_actions(self, obj: Protocol) -> list[str]:
        return obj.config_list("protected_actions")

    def get_allowed_while_halted(self, obj: Protocol) -> list[str]:
        return obj.config_list("allowed_while_halted")

    def get_min_evidence(self, obj: Protocol) -> int:
        return int((obj.config or {}).get("min_evidence") or 0)

    def get_appeal_window_seconds(self, obj: Protocol) -> int:
        return int((obj.config or {}).get("appeal_window_seconds") or 0)

    def get_reporter_bond_gen(self, obj: Protocol) -> str:
        return format_gen(obj.reporter_bond)

    def get_appeal_ends_at(self, obj: Protocol):
        """ISO datetime: halted_at + appeal_window_seconds. Null if not halted."""
        if obj.halted_at is None:
            return None
        window = self.get_appeal_window_seconds(obj)
        return obj.halted_at + timedelta(seconds=window)


class ProtocolDetailSerializer(ProtocolSerializer):
    """Detail adds the halting case inline so the status badge can explain itself."""

    active_case = serializers.SerializerMethodField()

    class Meta(ProtocolSerializer.Meta):
        fields = ProtocolSerializer.Meta.fields + ["active_case"]
        read_only_fields = fields

    def get_active_case(self, obj: Protocol) -> dict | None:
        from apps.cases.serializers import CaseSerializer

        if not obj.active_case_id:
            return None
        # Prefer the prefetch cache (obj.cases.filter() always hits the DB).
        cases = obj.cases.all()
        case = next(
            (c for c in cases if c.onchain_id == obj.active_case_id),
            None,
        )
        return CaseSerializer(case).data if case else None
