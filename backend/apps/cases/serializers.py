"""Frontend-ready case shapes (frozen for Phase 5 — additive changes only)."""

from rest_framework import serializers

from apps.cases.models import Case, CaseEvent
from apps.common.units import format_gen


class CaseEventSerializer(serializers.ModelSerializer):
    """Oldest-first timeline row. `id` is the on-chain event id."""

    id = serializers.IntegerField(source="onchain_id", read_only=True)
    case_id = serializers.SerializerMethodField()
    protocol_id = serializers.IntegerField(
        source="protocol_onchain_id", read_only=True
    )
    created_at = serializers.DateTimeField(
        source="chain_created_at", read_only=True
    )

    class Meta:
        model = CaseEvent
        fields = [
            "id",
            "case_id",
            "protocol_id",
            "event_type",
            "actor",
            "statement",
            "evidence_urls",
            "consensus_bool",
            "consensus_summary",
            "from_status",
            "to_status",
            "bond_amount",
            "bond_disposition",
            "created_at",
        ]
        read_only_fields = fields

    def get_case_id(self, obj: CaseEvent) -> int:
        # Prefer the mirrored snapshot so nested serialization needs no extra query.
        raw_id = (obj.raw or {}).get("case_id")
        if raw_id is not None:
            return int(raw_id)
        return obj.case.onchain_id


class CaseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="onchain_id", read_only=True)
    protocol_id = serializers.IntegerField(
        source="protocol_onchain_id", read_only=True
    )
    bond_amount_gen = serializers.SerializerMethodField()
    submitted_at = serializers.DateTimeField(
        source="chain_submitted_at", read_only=True
    )

    class Meta:
        model = Case
        fields = [
            "id",
            "protocol_id",
            "reporter",
            "allegation",
            "evidence_urls",
            "verdict_exploit",
            "verdict_summary",
            "status",
            "bond_amount",
            "bond_amount_gen",
            "bond_settled",
            "event_count",
            "submitted_at",
            "synced_at",
        ]
        read_only_fields = fields

    def get_bond_amount_gen(self, obj: Case) -> str:
        return format_gen(obj.bond_amount)


class CaseDetailSerializer(CaseSerializer):
    """Detail embeds protocol context plus the append-only event timeline."""

    protocol = serializers.SerializerMethodField()
    events = CaseEventSerializer(many=True, read_only=True)

    class Meta(CaseSerializer.Meta):
        fields = CaseSerializer.Meta.fields + ["protocol", "events"]
        read_only_fields = fields

    def get_protocol(self, obj: Case) -> dict:
        return {
            "id": obj.protocol.onchain_id,
            "name": obj.protocol.name,
            "status": obj.protocol.status,
            "governor": obj.protocol.governor,
        }
