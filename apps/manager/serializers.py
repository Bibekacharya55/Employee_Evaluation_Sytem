
from rest_framework import serializers

from .models import FinalReview


class FinalReviewCreateSerializer(serializers.Serializer):

    self_eval_id = serializers.IntegerField()

    comments = serializers.CharField()


class FinalReviewSerializer(serializers.ModelSerializer):

    manager_id = serializers.IntegerField(
        source="manager.id"
    )

    employee_id = serializers.IntegerField(
        source="employee.id"
    )

    self_eval_id = serializers.IntegerField(
        source="self_evaluation.id"
    )

    class Meta:
        model = FinalReview

        fields = [
            "id",
            "manager_id",
            "employee_id",
            "self_eval_id",
            "comments",
            "status",
            "review_date",
        ]