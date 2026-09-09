from django.urls import re_path

from apps.cases import views

urlpatterns = [
    re_path(r"^cases/?$", views.CaseListView.as_view(), name="case-list"),
    re_path(
        r"^cases/(?P<onchain_id>\d+)/?$",
        views.CaseDetailView.as_view(),
        name="case-detail",
    ),
]
