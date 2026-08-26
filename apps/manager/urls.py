from django.urls import path

from .views import (
    ManagerEmployeeReviewView,
    FinalReviewCreateView,
)


urlpatterns = [

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