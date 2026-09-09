"""
Health + fast-path sync endpoints.

`POST /api/sync/protocols/<id>` runs the sync **inline** (2–3 RPC reads) so the
frontend can call it right after a wallet tx is accepted and immediately read
the fresh status back. Celery beat still handles background drift.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from rest_framework import status as http_status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.cases.models import Case, CaseEvent
from apps.protocols.models import Protocol
from apps.protocols.serializers import ProtocolDetailSerializer
from apps.sync import indexer
from apps.sync.genlayer_client import ContractCallError, GenLayerError, get_reader
from apps.sync.models import SyncCursor
from apps.sync.serializers import SyncCursorSerializer

logger = logging.getLogger(__name__)

SECRET_HEADER = "X-Sync-Secret"


def _secret_ok(request) -> bool:
    expected = settings.SYNC_SHARED_SECRET
    if not expected:
        return True
    provided = request.headers.get(SECRET_HEADER) or request.query_params.get("secret")
    return provided == expected


def _forbidden() -> Response:
    return Response(
        {"detail": f"Missing or invalid {SECRET_HEADER}."},
        status=http_status.HTTP_403_FORBIDDEN,
    )


@api_view(["GET"])
def health(request):
    """GET /api/health — liveness plus indexer freshness."""
    database_ok = True
    database_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on deploy env
        database_ok = False
        database_error = str(exc)

    # Read-only: never create the cursor row from a health probe.
    cursor_row = SyncCursor.objects.first() if database_ok else None
    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": {"ok": database_ok, "error": database_error},
        "chain": {
            "rpc_url": settings.GENLAYER_RPC_URL,
            "chain_id": settings.GENLAYER_CHAIN_ID,
            "halt_module_address": settings.HALT_MODULE_ADDRESS,
            "demo_vault_address": settings.DEMO_VAULT_ADDRESS,
            "configured": bool(settings.HALT_MODULE_ADDRESS),
        },
        "indexed": {
            "protocols": Protocol.objects.count() if database_ok else None,
            "cases": Case.objects.count() if database_ok else None,
            "events": CaseEvent.objects.count() if database_ok else None,
        },
        "cursor": SyncCursorSerializer(cursor_row).data if cursor_row else None,
    }
    code = (
        http_status.HTTP_200_OK if database_ok else http_status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(payload, status=code)


@api_view(["POST"])
def sync_protocol(request, onchain_id: int):
    """POST /api/sync/protocols/<id> — inline resync of a protocol + its cases."""
    if not _secret_ok(request):
        return _forbidden()

    reader = get_reader()
    try:
        report = indexer.sync_protocol(int(onchain_id), reader=reader)
    except ContractCallError as exc:
        return Response(
            {"detail": f"Chain rejected the read: {exc}"},
            status=http_status.HTTP_404_NOT_FOUND,
        )
    except GenLayerError as exc:
        logger.warning("fast-path sync failed for protocol %s: %s", onchain_id, exc)
        return Response(
            {"detail": f"Could not reach GenLayer: {exc}"},
            status=http_status.HTTP_502_BAD_GATEWAY,
        )

    protocol = (
        Protocol.objects.prefetch_related("cases")
        .filter(onchain_id=int(onchain_id))
        .first()
    )
    return Response(
        {
            "synced": report.as_dict(),
            "protocol": ProtocolDetailSerializer(protocol).data if protocol else None,
        }
    )


@api_view(["POST"])
def sync_all(request):
    """POST /api/sync/all — full poll-and-diff pass (seeding / manual refresh)."""
    if not _secret_ok(request):
        return _forbidden()

    try:
        result = indexer.poll_and_diff(reader=get_reader())
    except GenLayerError as exc:
        logger.warning("full sync failed: %s", exc)
        return Response(
            {"detail": f"Could not reach GenLayer: {exc}"},
            status=http_status.HTTP_502_BAD_GATEWAY,
        )
    return Response({"synced": result})
