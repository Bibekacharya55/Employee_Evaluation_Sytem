from rest_framework import serializers

from .models import Category, Question


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "order",
        ]


class QuestionSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(
        source="category.id",
        read_only=True,
    )

    question_text = serializers.CharField(
        source="text",
        read_only=True,
    )

    display_order = serializers.IntegerField(
        source="order",
        read_only=True,
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "category_id",
            "question_text",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]