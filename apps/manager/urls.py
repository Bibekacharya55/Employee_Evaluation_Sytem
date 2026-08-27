from django.urls import path

from .views import (
    ManagerDashboardView,
    ManagerEmployeeReviewView,
    FinalReviewCreateView,
)


urlpatterns = [
    path(
        "dashboard/",
        ManagerDashboardView.as_view(),
        name="manager-dashboard",
    ),

    path(
        "employees/<int:employee_id>/review/",
        ManagerEmployeeReviewView.as_view(),
        name="manager-employee-review",
    ),

    path(
        "employees/<int:employee_id>/final-review/",
        FinalReviewCreateView.as_view(),
        name="manager-final-review",
    ),

]