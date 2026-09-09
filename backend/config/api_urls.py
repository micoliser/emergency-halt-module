"""
Public API routes. Shapes are frozen for the Phase 5 frontend — add routes,
do not rename or reshape existing ones (IMPLEMENTATION_PLAN.md Phase 4 fallback note).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.protocols.urls")),
    path("", include("apps.cases.urls")),
    path("", include("apps.sync.urls")),
]
