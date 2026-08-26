from django.contrib import admin

from .models import FinalReview


@admin.register(FinalReview)
class FinalReviewAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "manager",
        "employee",
        "self_evaluation",
        "status",
        "review_date",
    ]

    list_filter = [
        "status",
        "review_date",
    ]

    search_fields = [
        "manager__email",
        "employee__email",
    ]