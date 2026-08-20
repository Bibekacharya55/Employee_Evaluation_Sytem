from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Category, Question
from .serializers import CategorySerializer, QuestionSerializer


class QuestionListView(ListAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Question.objects.select_related("category").all()

        category_id = self.request.query_params.get("category")

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset


class CategoryListView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]