from django.urls import path

from .views import (
    AnswerDetailView,
    AvailableEmployeesView,
    EvaluationCreateView,
    EvaluationCycleListView,
    EvaluationDetailView,
    PeerAssignmentCreateView,
    MyPeerAssignmentsView,
    SaveAnswersView,
    SubmitEvaluationView,
    
)

urlpatterns = [
    # GET /api/evaluation-cycles/  (supports ?status=open)
    path("api/evaluation-cycles/", EvaluationCycleListView.as_view(), name="evaluation-cycle-list"),
    # GET /api/peer-assignments/available-employees/?cycle_id=&search=
    path(
        "api/peer-assignments/available-employees/",
        AvailableEmployeesView.as_view(),
        name="peer-assignment-available-employees",
    ),
    # POST /api/peer-assignments/
    path("api/peer-assignments/", PeerAssignmentCreateView.as_view(), name="peer-assignment-create"),
    # POST /api/evaluations/
    path("api/evaluations/", EvaluationCreateView.as_view(), name="evaluation-create"),
    # PATCH /api/evaluations/{id}/answers/
    path(
        "api/evaluations/<int:pk>/answers/",
        SaveAnswersView.as_view(),
        name="evaluation-save-answers",
    ),
    # POST /api/evaluations/{id}/submit/
    path(
        "api/evaluations/<int:pk>/submit/",
        SubmitEvaluationView.as_view(),
        name="evaluation-submit",
    ),
    # GET /api/evaluations/{id}/
    path("api/evaluations/<int:pk>/", EvaluationDetailView.as_view(), name="evaluation-detail"),
    # GET /api/answers/{id}/
    path("api/answers/<int:pk>/", AnswerDetailView.as_view(), name="answer-detail"),
    
    path(
    "peer-assignments/my/",
    MyPeerAssignmentsView.as_view(),
    name="my-peer-assignments",
),
]
