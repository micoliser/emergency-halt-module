from rest_framework import serializers

from apps.sync.models import SyncCursor


class SyncCursorSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncCursor
        fields = [
            "protocol_count",
            "case_count",
            "case_event_count",
            "last_run_at",
            "last_success_at",
            "last_error",
            "contract_address",
        ]
        read_only_fields = fields
