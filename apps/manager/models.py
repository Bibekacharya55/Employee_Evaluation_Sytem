from django.conf import settings
from django.db import models

from apps.evaluations.models import Evaluation


class FinalReview(models.Model):

    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
    ]

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="final_reviews_as_manager",
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="final_reviews_as_employee",
    )

    self_evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="final_reviews",
    )

    comments = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
    )

    review_date = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employee",
                    "self_evaluation",
                ],
                name="unique_final_review_per_self_evaluation",
            )
        ]