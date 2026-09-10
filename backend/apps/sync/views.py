"""
Health + fast-path sync endpoints.

`POST /api/sync/protocols/<id>` runs the sync **inline** (2–3 RPC reads) so the
frontend can call it right after a wallet tx is accepted and immediately read
the fresh status back. Celery beat still handles background drift.
"""

from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.db import connection
from rest_framework import status as http_status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from apps.cases.models import Case, CaseEvent
from apps.protocols.models import Protocol
from apps.protocols.serializers import ProtocolDetailSerializer
from apps.sync import indexer
from apps.sync.genlayer_client import ContractCallError, GenLayerError, get_reader
from apps.sync.models import SyncCursor
from apps.sync.throttles import SyncRateThrottle

logger = logging.getLogger(__name__)

SECRET_HEADER = "X-Sync-Secret"


def _secret_ok(request) -> bool:
    """
    Gate sync POSTs.

    - Non-empty SYNC_SHARED_SECRET: require matching X-Sync-Secret header
      (header only — never query string).
    - Empty secret: allowed only when DEBUG=True (local). Production refuses
      to boot without a secret (see settings.py).
    """
    expected = settings.SYNC_SHARED_SECRET or ""
    if not expected:
        return bool(settings.DEBUG)

    provided = request.headers.get(SECRET_HEADER) or ""
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


def _forbidden() -> Response:
    return Response(
        {"detail": f"Missing or invalid {SECRET_HEADER}."},
        status=http_status.HTTP_403_FORBIDDEN,
    )


@api_view(["GET"])
def health(request):
    """
    GET /api/health — public liveness.

    Omits RPC URL, DB exception text, and cursor last_error (ops detail).
    Contract addresses are public on-chain and remain listed for the demo UI.
    """
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on deploy env
        database_ok = False
        logger.warning("health database probe failed: %s", exc)

    cursor_row = SyncCursor.objects.first() if database_ok else None
    configured_addr = (settings.HALT_MODULE_ADDRESS or "").lower()
    stored_addr = (cursor_row.contract_address or "").lower() if cursor_row else ""
    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": {"ok": database_ok},
        "chain": {
            "chain_id": settings.GENLAYER_CHAIN_ID,
            "halt_module_address": settings.HALT_MODULE_ADDRESS,
            "demo_vault_address": settings.DEMO_VAULT_ADDRESS,
            "configured": bool(settings.HALT_MODULE_ADDRESS),
            "address_match": (
                None
                if not stored_addr or not configured_addr
                else stored_addr == configured_addr
            ),
        },
        "indexed": {
            "protocols": Protocol.objects.count() if database_ok else None,
            "cases": Case.objects.count() if database_ok else None,
            "events": CaseEvent.objects.count() if database_ok else None,
        },
        "cursor": (
            {
                "protocol_count": cursor_row.protocol_count,
                "case_count": cursor_row.case_count,
                "case_event_count": cursor_row.case_event_count,
                "last_success_at": cursor_row.last_success_at,
                "has_error": bool(cursor_row.last_error),
            }
            if cursor_row
            else None
        ),
    }
    code = (
        http_status.HTTP_200_OK if database_ok else http_status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return Response(payload, status=code)


@api_view(["POST"])
@throttle_classes([SyncRateThrottle])
def sync_protocol(request, onchain_id: int):
    """POST /api/sync/protocols/<id> — inline resync of a protocol + its cases."""
    if not _secret_ok(request):
        return _forbidden()

    reader = get_reader()
    try:
        report = indexer.sync_protocol(int(onchain_id), reader=reader)
    except ContractCallError as exc:
        logger.info("fast-path sync rejected for protocol %s: %s", onchain_id, exc)
        return Response(
            {"detail": "Protocol not found on the configured Halt Module."},
            status=http_status.HTTP_404_NOT_FOUND,
        )
    except GenLayerError as exc:
        logger.warning("fast-path sync failed for protocol %s: %s", onchain_id, exc)
        return Response(
            {"detail": "Could not reach GenLayer. Try again shortly."},
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
@throttle_classes([SyncRateThrottle])
def sync_all(request):
    """POST /api/sync/all — full poll-and-diff pass (seeding / manual refresh)."""
    if not _secret_ok(request):
        return _forbidden()

    try:
        result = indexer.poll_and_diff(reader=get_reader())
    except GenLayerError as exc:
        logger.warning("full sync failed: %s", exc)
        return Response(
            {"detail": "Could not reach GenLayer. Try again shortly."},
            status=http_status.HTTP_502_BAD_GATEWAY,
        )
    return Response({"synced": result})
