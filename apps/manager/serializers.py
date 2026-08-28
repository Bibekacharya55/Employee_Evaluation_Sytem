from rest_framework import serializers
from .models import FinalReview


class FinalReviewCreateSerializer(serializers.Serializer):
    self_eval_id = serializers.IntegerField()
    justification = serializers.CharField()


class FinalReviewSerializer(serializers.ModelSerializer):
    # Added read_only=True to source fields to avoid write-validation issues
    manager_id = serializers.IntegerField(source="manager.id", read_only=True)
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    self_eval_id = serializers.IntegerField(source="self_evaluation.id", read_only=True)

    employee_name = serializers.CharField(
        source="employee.get_full_name", read_only=True
    )
    designation = serializers.CharField(source="employee.role", read_only=True)
    evaluator_name = serializers.CharField(
        source="manager.get_full_name", read_only=True
    )
    overall_score = serializers.FloatField(
        source="final_score", read_only=True, default=None
    )

    class Meta:
        model = FinalReview
        fields = [
            "id",
            "manager_id",
            "employee_id",
            "employee_name",
            "designation",
            "evaluator_name",
            "self_eval_id",
            "overall_score",
            "justification",
            "status",
            "review_date",
        ]
