from django.http import JsonResponse
from django.urls import include, path


def root(_request):
    return JsonResponse(
        {
            "service": "emergency-halt-module-indexer",
            "docs": "backend/README.md",
            "routes": [
                "GET  /api/health",
                "GET  /api/protocols?offset=&limit=",
                "GET  /api/protocols/<id>",
                "GET  /api/protocols/<id>/cases?offset=&limit=",
                "GET  /api/cases?offset=&limit=&protocol_id=",
                "GET  /api/cases/<id>",
                "POST /api/sync/protocols/<id>",
                "POST /api/sync/all",
            ],
        }
    )


urlpatterns = [
    path("", root),
    path("api/", include("config.api_urls")),
]
