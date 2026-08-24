from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from questions.models import Question


class EvaluationCycle(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
    ]

    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return self.name


class PeerAssignment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
    ]

    cycle = models.ForeignKey(
        EvaluationCycle,
        on_delete=models.CASCADE,
        related_name="peer_assignments",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="peer_assignments_as_evaluator",
    )
    evaluatee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="peer_assignments_as_evaluatee",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["cycle", "evaluator", "evaluatee"]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.evaluator} → {self.evaluatee} ({self.cycle})"


class Evaluation(models.Model):
    TYPE_SELF = "self"
    TYPE_PEER = "peer"

    TYPE_CHOICES = [
        (TYPE_SELF, "Self"),
        (TYPE_PEER, "Peer"),
    ]

    STATUS_NOT_STARTED = "not_started"
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_DIFF_REVIEW = "diff-review"
    STATUS_DIFF_REVIEW_2 = "diff-review-2"
    STATUS_LOCKED = "locked"

    STATUS_CHOICES = [  # noqa: RUF012
        (STATUS_NOT_STARTED, "Not Started"),
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_DIFF_REVIEW, "Diff Review"),
        (STATUS_DIFF_REVIEW_2, "Diff Review 2"),
        (STATUS_LOCKED, "Locked"),
    ]

    cycle = models.ForeignKey(
        EvaluationCycle,
        on_delete=models.CASCADE,
        related_name="evaluations",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="evaluations_as_evaluator",
    )
    evaluatee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="evaluations_as_evaluatee",
    )
    peer_assignment = models.ForeignKey(
        PeerAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluations",
    )
    evaluation_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.evaluation_type} evaluation by {self.evaluator} for {self.evaluatee}"


class Answer(models.Model):
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="answers",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )

    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    justification = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["evaluation", "question"]
        ordering = ["question__order", "id"]

    def __str__(self):
        return f"Answer to Q{self.question_id} for evaluation {self.evaluation_id}"


