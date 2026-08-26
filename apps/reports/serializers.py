from rest_framework import serializers


class ReportListSerializer(serializers.Serializer):

    evaluation_id = serializers.IntegerField()
    employee = serializers.CharField()
    evaluating = serializers.CharField()
    status = serializers.CharField()
    overall_score = serializers.FloatField()


class ReportDetailSerializer(serializers.Serializer):

    evaluatee = serializers.DictField()
    evaluator = serializers.DictField()
    status = serializers.CharField()
    overall_score = serializers.FloatField()
    categories = serializers.ListField()