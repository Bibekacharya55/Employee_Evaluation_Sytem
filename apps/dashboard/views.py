from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.evaluations.models import Evaluation, EvaluationCycle
from apps.questions.models import Question

from .serializers import EmployeeDashboardSerializer


class DashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        # Manager gets the same dashboard as employee
        # plus manager-specific access.
        if (
            user.role == "manager"
            or user.is_superuser
        ):
            return self.dashboard(
                user=user,
                role="manager",
                manager_access=True,
            )

        # Normal employee dashboard
        return self.dashboard(
            user=user,
            role="employee",
            manager_access=False,
        )

    def dashboard(
        self,
        user,
        role,
        manager_access=False,
    ):

        # ---------------------------------------
        # 1. Get current/open evaluation cycle
        # ---------------------------------------

        cycle = EvaluationCycle.objects.filter(
            status=EvaluationCycle.STATUS_OPEN
        ).first()

        # ---------------------------------------
        # No open cycle
        # ---------------------------------------

        if not cycle:

            data = {
                "role": role,

                "cycle": None,

                "counts": {
                    "in_progress": 0,
                    "submitted": 0,
                },

                "to_do": [],

                "completed": [],
            }

            # Only manager receives manager access
            if manager_access:
                data["manager_access"] = {
                    "can_review_employees": True,
                    "can_final_review": True,
                    "can_view_reports": True,
                    "can_export_reports": True,
                }

            serializer = EmployeeDashboardSerializer(data)

            return Response(serializer.data)

        # ---------------------------------------
        # 2. Get evaluations of logged-in user
        # ---------------------------------------

        evaluations = Evaluation.objects.filter(
            cycle=cycle,
            evaluator=user,
        ).select_related(
            "evaluatee"
        )

        # ---------------------------------------
        # 3. Total active questions
        # ---------------------------------------

        total_questions = Question.objects.filter(
            is_active=True
        ).count()

        # ---------------------------------------
        # 4. Evaluation statuses
        # ---------------------------------------

        in_progress_statuses = [
            Evaluation.STATUS_NOT_STARTED,
            Evaluation.STATUS_DRAFT,
            Evaluation.STATUS_DIFF_REVIEW,
            Evaluation.STATUS_DIFF_REVIEW_2,
        ]

        completed_statuses = [
            Evaluation.STATUS_SUBMITTED,
            Evaluation.STATUS_LOCKED,
        ]

        # ---------------------------------------
        # 5. Counts
        # ---------------------------------------

        in_progress = evaluations.filter(
            status__in=in_progress_statuses
        ).count()

        completed_count = evaluations.filter(
            status__in=completed_statuses
        ).count()

        # ---------------------------------------
        # 6. To-do evaluations
        # ---------------------------------------

        to_do = []

        for evaluation in evaluations.filter(
            status__in=in_progress_statuses
        ):

            evaluatee = None

            # Self evaluation
            if evaluation.evaluation_type == Evaluation.TYPE_SELF:

                evaluatee = None

            # Peer evaluation
            elif evaluation.evaluation_type == Evaluation.TYPE_PEER:

                evaluatee = {
                    "id": evaluation.evaluatee.id,
                    "first_name": evaluation.evaluatee.first_name,
                    "last_name": evaluation.evaluatee.last_name,
                    "designation": evaluation.evaluatee.designation,
                }

            to_do.append({
                "evaluation_id": evaluation.id,

                "evaluation_type": evaluation.evaluation_type,

                "evaluatee": evaluatee,

                "status": evaluation.status,

                "answered_count": evaluation.answers.count(),

                "total_questions": total_questions,
            })

        # ---------------------------------------
        # 7. Completed evaluations
        # ---------------------------------------

        completed = []

        for evaluation in evaluations.filter(
            status__in=completed_statuses
        ):

            evaluatee = None

            # Self evaluation
            if evaluation.evaluation_type == Evaluation.TYPE_SELF:

                evaluatee = None

            # Peer evaluation
            elif evaluation.evaluation_type == Evaluation.TYPE_PEER:

                evaluatee = {
                    "id": evaluation.evaluatee.id,
                    "first_name": evaluation.evaluatee.first_name,
                    "last_name": evaluation.evaluatee.last_name,
                    "designation": evaluation.evaluatee.designation,
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

        # ---------------------------------------
        # 8. Final dashboard response
        # ---------------------------------------

        data = {
            "role": role,

            "cycle": {
                "id": cycle.id,
                "name": cycle.name,
                "status": cycle.status,
                "start_date": cycle.start_date,
                "end_date": cycle.end_date,
            },

            "counts": {
                "in_progress": in_progress,
                "completed": completed_count
            },

            "to_do": to_do,

            "completed": completed,
        }

        # ---------------------------------------
        # 9. Manager-only capabilities
        # ---------------------------------------

        if manager_access:

            data["manager_access"] = {
                "can_review_employees": True,
                "can_final_review": True,
                "can_view_reports": True,
                "can_export_reports": True,
            }

        # ---------------------------------------
        # 10. Serialize response
        # ---------------------------------------

        serializer = EmployeeDashboardSerializer(data)

        return Response(serializer.data)