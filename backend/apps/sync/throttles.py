"""HTTP rate limits for sync POSTs (GenLayer RPC is expensive)."""

from rest_framework.throttling import AnonRateThrottle


class SyncRateThrottle(AnonRateThrottle):
    scope = "sync"
