from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.cases.models import Case
from apps.cases.serializers import CaseSerializer
from apps.common.units import normalize_address
from apps.protocols.models import Protocol
from apps.protocols.serializers import ProtocolDetailSerializer, ProtocolSerializer


class ProtocolListView(generics.ListAPIView):
    """GET /api/protocols?offset=&limit=&status=&governor="""

    serializer_class = ProtocolSerializer

    def get_queryset(self):
        queryset = Protocol.objects.all()
        status = self.request.query_params.get("status")
        governor = self.request.query_params.get("governor")
        if status:
            queryset = queryset.filter(status=status.upper())
        if governor:
            # Stored as normalize_address() (0x + 40 hex); bare/unpadded query must match.
            queryset = queryset.filter(governor=normalize_address(governor))
        return queryset


class ProtocolDetailView(generics.RetrieveAPIView):
    """GET /api/protocols/<id>"""

    serializer_class = ProtocolDetailSerializer
    # Prefetch so get_active_case() can resolve without a second query.
    queryset = Protocol.objects.prefetch_related("cases")
    lookup_field = "onchain_id"
    lookup_url_kwarg = "onchain_id"


class ProtocolCasesView(generics.ListAPIView):
    """GET /api/protocols/<id>/cases?offset=&limit=&status="""

    serializer_class = CaseSerializer

    def get_queryset(self):
        protocol = get_object_or_404(
            Protocol, onchain_id=self.kwargs["onchain_id"]
        )
        queryset = Case.objects.filter(protocol=protocol)
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status.upper())
        return queryset
