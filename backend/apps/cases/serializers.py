"""Frontend-ready case shapes (frozen for Phase 5 — additive changes only)."""

from rest_framework import serializers

from apps.cases.models import Case
from apps.common.units import format_gen


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
            "submitted_at",
            "synced_at",
        ]
        read_only_fields = fields

    def get_bond_amount_gen(self, obj: Case) -> str:
        return format_gen(obj.bond_amount)


class CaseDetailSerializer(CaseSerializer):
    """Detail embeds just enough protocol context to render the case page."""

    protocol = serializers.SerializerMethodField()

    class Meta(CaseSerializer.Meta):
        fields = CaseSerializer.Meta.fields + ["protocol"]
        read_only_fields = fields

    def get_protocol(self, obj: Case) -> dict:
        return {
            "id": obj.protocol.onchain_id,
            "name": obj.protocol.name,
            "status": obj.protocol.status,
            "governor": obj.protocol.governor,
        }
