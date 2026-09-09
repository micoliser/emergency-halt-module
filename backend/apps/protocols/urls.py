from django.urls import re_path

from apps.protocols import views

urlpatterns = [
    re_path(r"^protocols/?$", views.ProtocolListView.as_view(), name="protocol-list"),
    re_path(
        r"^protocols/(?P<onchain_id>\d+)/?$",
        views.ProtocolDetailView.as_view(),
        name="protocol-detail",
    ),
    re_path(
        r"^protocols/(?P<onchain_id>\d+)/cases/?$",
        views.ProtocolCasesView.as_view(),
        name="protocol-cases",
    ),
]
