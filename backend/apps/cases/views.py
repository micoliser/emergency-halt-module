from rest_framework import generics

from apps.cases.models import Case
from apps.cases.serializers import CaseDetailSerializer, CaseSerializer
from apps.common.units import normalize_address


class CaseListView(generics.ListAPIView):
    """GET /api/cases?offset=&limit=&protocol_id=&status=&reporter="""

    serializer_class = CaseSerializer

    def get_queryset(self):
        queryset = Case.objects.select_related("protocol")
        params = self.request.query_params
        protocol_id = params.get("protocol_id")
        status = params.get("status")
        reporter = params.get("reporter")
        if protocol_id and protocol_id.isdigit():
            queryset = queryset.filter(protocol_onchain_id=int(protocol_id))
        if status:
            queryset = queryset.filter(status=status.upper())
        if reporter:
            # Stored as normalize_address() (0x + 40 hex); bare/unpadded query must match.
            queryset = queryset.filter(reporter=normalize_address(reporter))
        return queryset


class CaseDetailView(generics.RetrieveAPIView):
    """GET /api/cases/<id> — includes `events` oldest-first (prefetched)."""

    serializer_class = CaseDetailSerializer
    queryset = Case.objects.select_related("protocol").prefetch_related("events")
    lookup_field = "onchain_id"
    lookup_url_kwarg = "onchain_id"
