from django.urls import path

from .views import (
    ReportListView,
    ReportDetailView,
    ReportExportView,
)


urlpatterns = [

    # GET /api/reports/?cycle_id=3
    path(
        "",
        ReportListView.as_view(),
        name="report-list",
    ),

    # GET /api/reports/102/
    path(
        "<int:evaluation_id>/",
        ReportDetailView.as_view(),
        name="report-detail",
    ),

    # GET /api/reports/export/?cycle_id=3&format=csv
    path(
        "export/",
        ReportExportView.as_view(),
        name="report-export",
    ),
]