from django.urls import path

from .views import CategoryListView, QuestionListView


urlpatterns = [
    path(
        "questions/",
        QuestionListView.as_view(),
        name="question-list",
    ),
    path(
        "question-categories/",
        CategoryListView.as_view(),
        name="category-list",
    ),
]