from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from evaluations.models import Evaluation, EvaluationCycle
from questions.models import Question

from .serializers import EmployeeDashboardSerializer

class DashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        if request.user.is_staff:
            return self.manager_dashboard(request.user)

        return self.employee_dashboard(request.user)

    def employee_dashboard(self, user):

        cycle = EvaluationCycle.objects.filter(
            status=EvaluationCycle.STATUS_OPEN
        ).first()

        if not cycle:
            return Response({
                "role": "employee",
                "cycle": None,
                "counts": {
                    "in_progress": 0,
                    "submitted": 0,
                },
                "to_do": [],
                "completed": [],
            })

        evaluations = Evaluation.objects.filter(
            cycle=cycle,
            evaluator=user,
        ).select_related(
            "evaluatee"
        )

        total_questions = Question.objects.filter(
            is_active=True
        ).count()

        in_progress_statuses = [
            Evaluation.STATUS_NOT_STARTED,
            Evaluation.STATUS_DRAFT,
        ]

        completed_statuses = [
            Evaluation.STATUS_SUBMITTED,
            Evaluation.STATUS_DIFF_REVIEW,
            Evaluation.STATUS_DIFF_REVIEW_2,
            Evaluation.STATUS_LOCKED,
        ]

        in_progress = evaluations.filter(
            status__in=in_progress_statuses
        ).count()

        submitted = evaluations.filter(
            status=Evaluation.STATUS_SUBMITTED
        ).count()

        to_do = []

        for evaluation in evaluations.filter(
            status__in=in_progress_statuses
        ):

            evaluatee = None

            if evaluation.evaluation_type == Evaluation.TYPE_PEER:
                evaluatee = {
                    "id": evaluation.evaluatee.id,
                    "first_name": evaluation.evaluatee.first_name,
                    "last_name": evaluation.evaluatee.last_name,
                }

            to_do.append({
                "evaluation_id": evaluation.id,
                "evaluation_type": evaluation.evaluation_type,
                "evaluatee": evaluatee,
                "status": evaluation.status,
                "answered_count": evaluation.answers.count(),
                "total_questions": total_questions,
            })

        completed = []

        for evaluation in evaluations.filter(
            status__in=completed_statuses
        ):

            evaluatee = None

            if evaluation.evaluation_type == Evaluation.TYPE_PEER:
                evaluatee = {
                    "id": evaluation.evaluatee.id,
                    "first_name": evaluation.evaluatee.first_name,
                    "last_name": evaluation.evaluatee.last_name,
                }

            completed.append({
                "evaluation_id": evaluation.id,
                "evaluation_type": evaluation.evaluation_type,
                "evaluatee": evaluatee,
                "status": evaluation.status,
                "requires_score_check": evaluation.status in [
                    Evaluation.STATUS_DIFF_REVIEW,
                    Evaluation.STATUS_DIFF_REVIEW_2,
                ],
            })

        data = {
            "role": "employee",

            "cycle": {
                "id": cycle.id,
                "name": cycle.name,
                "status": cycle.status,
                "start_date": cycle.start_date,
                "end_date": cycle.end_date,
            },

            "counts": {
                "in_progress": in_progress,
                "submitted": submitted,
            },

            "to_do": to_do,

            "completed": completed,
        }

        serializer = EmployeeDashboardSerializer(data)

        return Response(serializer.data)