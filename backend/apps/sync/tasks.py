"""
Celery tasks — thin wrappers around `apps.sync.indexer`.

Run them with:
    celery -A config worker -l info
    celery -A config beat -l info

Retry policy: transport/rate-limit failures (`GenLayerError`) are retried;
contract reverts (`ContractCallError`, e.g. a wrong address or a protocol id
that does not exist) are permanent, so they are logged and returned instead of
spinning the queue.
"""

from __future__ import annotations

import logging
from functools import wraps

from celery import shared_task

from apps.sync import indexer
from apps.sync.genlayer_client import ContractCallError, GenLayerError

logger = logging.getLogger(__name__)

RETRY_KWARGS = {"max_retries": 3, "countdown": 10}


def rpc_task(name: str):
    """Register a task with the shared RPC error policy."""

    def decorator(func):
        @shared_task(name=name, bind=True)
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ContractCallError as exc:
                logger.error("%s: chain rejected the read: %s", name, exc)
                return {"error": str(exc), "retried": False}
            except GenLayerError as exc:
                logger.warning("%s: RPC failure, retrying: %s", name, exc)
                raise self.retry(exc=exc, **RETRY_KWARGS)

        return wrapper

    return decorator


@rpc_task("apps.sync.tasks.poll_and_diff")
def poll_and_diff():
    """Beat entrypoint: counts → new pages → refresh changed rows."""
    return indexer.poll_and_diff()


@rpc_task("apps.sync.tasks.sync_counts")
def sync_counts():
    return indexer.sync_counts()


@rpc_task("apps.sync.tasks.sync_protocols_page")
def sync_protocols_page(offset: int = 0, limit: int | None = None):
    return indexer.sync_protocols_page(offset, limit).as_dict()


@rpc_task("apps.sync.tasks.sync_cases_page")
def sync_cases_page(offset: int = 0, limit: int | None = None):
    return indexer.sync_cases_page(offset, limit).as_dict()


@rpc_task("apps.sync.tasks.sync_protocol")
def sync_protocol(protocol_id: int):
    """Background twin of the `POST /api/sync/protocols/<id>` fast path."""
    return indexer.sync_protocol(int(protocol_id)).as_dict()


@rpc_task("apps.sync.tasks.sync_case")
def sync_case(case_id: int):
    return indexer.sync_case(int(case_id)).as_dict()
