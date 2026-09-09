"""
Offset/limit pagination matching the contract view signatures
(`list_protocols(offset, limit)`), capped at the contract's MAX_PAGE_LIMIT.
"""

from django.conf import settings
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class OffsetLimitPagination(LimitOffsetPagination):
    limit_query_param = "limit"
    offset_query_param = "offset"

    def get_limit(self, request):
        # Read the caps at request time so both are env-driven and stay in
        # step with the contract's page limit.
        self.default_limit = getattr(settings, "API_DEFAULT_PAGE_SIZE", 20)
        self.max_limit = getattr(settings, "API_MAX_PAGE_SIZE", 50)
        return super().get_limit(request)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.count,
                "offset": self.offset,
                "limit": self.limit,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
