from rest_framework import serializers


class DashboardEvaluateeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    designation = serializers.CharField()


class DashboardTodoSerializer(serializers.Serializer):
    evaluation_id = serializers.IntegerField()
    evaluation_type = serializers.CharField()
    evaluatee = DashboardEvaluateeSerializer(
        allow_null=True
    )
    status = serializers.CharField()
    answered_count = serializers.IntegerField()
    total_questions = serializers.IntegerField()


class DashboardCompletedSerializer(serializers.Serializer):
    evaluation_id = serializers.IntegerField()
    evaluation_type = serializers.CharField()
    evaluatee = DashboardEvaluateeSerializer(
        allow_null=True
    )
    status = serializers.CharField()
    requires_score_check = serializers.BooleanField()


class EmployeeDashboardSerializer(serializers.Serializer):
    role = serializers.CharField()

    cycle = serializers.DictField(
        allow_null=True
    )

    counts = serializers.DictField()

    to_do = DashboardTodoSerializer(
        many=True
    )

    completed = DashboardCompletedSerializer(
        many=True
    )

    manager_access = serializers.DictField(
        required=False
    )