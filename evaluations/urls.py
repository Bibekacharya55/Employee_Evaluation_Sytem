from django.urls import path

from .views import (
    AnswerDetailView,
    AvailableEmployeesView,
    EvaluationCreateView,
    EvaluationCycleListView,
    EvaluationDetailView,
    EvaluationMineView,
    PeerAssignmentCreateView,
    SaveAnswersView,
    SubmitEvaluationView,
)

urlpatterns = [
    # GET /api/evaluation-cycles/ and /evaluation-cycles/
    path("api/evaluation-cycles/", EvaluationCycleListView.as_view(), name="evaluation-cycle-list"),
    path("evaluation-cycles/", EvaluationCycleListView.as_view()),

    # GET /api/peer-assignments/available-employees/
    path(
        "api/peer-assignments/available-employees/",
        AvailableEmployeesView.as_view(),
        name="peer-assignment-available-employees",
    ),
    path(
        "peer-assignments/available-employees/",
        AvailableEmployeesView.as_view(),
    ),

    # POST /api/peer-assignments/
    path("api/peer-assignments/", PeerAssignmentCreateView.as_view(), name="peer-assignment-create"),
    path("peer-assignments/", PeerAssignmentCreateView.as_view()),

    # GET /api/evaluations/mine/ and /evaluations/mine/
    path("api/evaluations/mine/", EvaluationMineView.as_view(), name="evaluation-mine"),
    path("evaluations/mine/", EvaluationMineView.as_view()),

    # POST /api/evaluations/ and /evaluations/
    path("api/evaluations/", EvaluationCreateView.as_view(), name="evaluation-create"),
    path("evaluations/", EvaluationCreateView.as_view()),

    # PATCH /api/evaluations/{id}/answers/ and /evaluations/{id}/answers/
    path(
        "api/evaluations/<int:pk>/answers/",
        SaveAnswersView.as_view(),
        name="evaluation-save-answers",
    ),
    path(
        "evaluations/<int:pk>/answers/",
        SaveAnswersView.as_view(),
    ),

    # POST /api/evaluations/{id}/submit/ and /evaluations/{id}/submit/
    path(
        "api/evaluations/<int:pk>/submit/",
        SubmitEvaluationView.as_view(),
        name="evaluation-submit",
    ),
    path(
        "evaluations/<int:pk>/submit/",
        SubmitEvaluationView.as_view(),
    ),

    # GET /api/evaluations/{id}/ and /evaluations/{id}/
    path("api/evaluations/<int:pk>/", EvaluationDetailView.as_view(), name="evaluation-detail"),
    path("evaluations/<int:pk>/", EvaluationDetailView.as_view()),

    # GET /api/answers/{id}/
    path("api/answers/<int:pk>/", AnswerDetailView.as_view(), name="answer-detail"),
    path("answers/<int:pk>/", AnswerDetailView.as_view()),
]
