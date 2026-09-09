from django.urls import re_path

from apps.sync import views

urlpatterns = [
    re_path(r"^health/?$", views.health, name="health"),
    re_path(
        r"^sync/protocols/(?P<onchain_id>\d+)/?$",
        views.sync_protocol,
        name="sync-protocol",
    ),
    re_path(r"^sync/all/?$", views.sync_all, name="sync-all"),
]
