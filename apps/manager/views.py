from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.evaluations.models import Evaluation, EvaluationCycle, PeerAssignment
from apps.evaluations.serializers import EvaluationDetailSerializer

from .models import FinalReview
from .permissions import IsManager
from .serializers import (
    FinalReviewCreateSerializer,
    FinalReviewSerializer,
)


def _check_ready_for_final_review(cycle, employee, self_eval, peer_evals):
    if not self_eval or self_eval.status != Evaluation.STATUS_LOCKED:
        return False

    if not peer_evals:
        return False

    if any(pe.status != Evaluation.STATUS_LOCKED for pe in peer_evals):
        return False

    peer_assignments = list(
        PeerAssignment.objects.filter(
            cycle=cycle,
            evaluatee=employee,
        )
    )
    if peer_assignments:
        locked_assignment_ids = {
            pe.peer_assignment_id
            for pe in peer_evals
            if pe.status == Evaluation.STATUS_LOCKED
        }
        if any(pa.id not in locked_assignment_ids for pa in peer_assignments):
            return False

    return True


class ManagerDashboardView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManager,
    ]

    def get(self, request):
        cycle = EvaluationCycle.objects.filter(
            status=EvaluationCycle.STATUS_OPEN
        ).first()

        if not cycle:
            cycle = EvaluationCycle.objects.order_by("-start_date", "-id").first()

        if not cycle:
            return Response(
                {
                    "metrics": {
                        "all": 0,
                        "to_do": 0,
                        "in_progress": 0,
                        "completed": 0,
                    },
                    "evaluations": [],
                }
            )

        evaluatee_ids = set(
            Evaluation.objects.filter(cycle=cycle).values_list(
                "evaluatee_id", flat=True
            )
        ).union(
            PeerAssignment.objects.filter(cycle=cycle).values_list(
                "evaluatee_id", flat=True
            )
        )

        if evaluatee_ids:
            employees = User.objects.filter(
                id__in=evaluatee_ids, is_active=True
            ).order_by("id")
        else:
            employees = User.objects.filter(is_active=True).order_by("id")

        results = []

        # Metric counters for the top summary cards
        todo_count = 0
        in_progress_count = 0
        completed_count = 0

        for employee in employees:
            self_evaluation = Evaluation.objects.filter(
                cycle=cycle,
                evaluator=employee,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_SELF,
            ).first()

            peer_evaluations = list(
                Evaluation.objects.filter(
                    cycle=cycle,
                    evaluatee=employee,
                    evaluation_type=Evaluation.TYPE_PEER,
                ).select_related("evaluator")
            )

            final_review = (
                FinalReview.objects.filter(self_evaluation=self_evaluation).first()
                if self_evaluation
                else None
            )

            # Determine status string matching UI badges (Submitted, To Do, In Progress)
            if final_review or (
                self_evaluation and self_evaluation.status == Evaluation.STATUS_LOCKED
            ):
                table_status = "Submitted"
                completed_count += 1
            elif self_evaluation:
                table_status = "In Progress"
                in_progress_count += 1
            else:
                table_status = "To Do"
                todo_count += 1

            evaluator_name = None
            if peer_evaluations and peer_evaluations[0].evaluator:
                evaluator_name = f"{peer_evaluations[0].evaluator.first_name} {peer_evaluations[0].evaluator.last_name}".strip()
            elif final_review and final_review.manager:
                evaluator_name = f"{final_review.manager.first_name} {final_review.manager.last_name}".strip()

            review_date = None
            if final_review and getattr(final_review, "review_date", None):
                review_date = final_review.review_date.strftime("%d %B, %Y")
            elif self_evaluation and getattr(self_evaluation, "updated_at", None):
                review_date = self_evaluation.updated_at.strftime("%d %B, %Y")

            overall_score = (
                getattr(final_review, "final_score", None) if final_review else None
            )
            designation = getattr(employee, "role", None) or getattr(
                employee, "designation", "Developer"
            )

            results.append(
                {
                    "employee": {
                        "id": employee.id,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "designation": designation,
                    },
                    "evaluator_name": evaluator_name or "N/A",
                    "status": table_status,
                    "overall_score": overall_score,
                    "date": review_date,
                    "ready_for_final_review": _check_ready_for_final_review(
                        cycle, employee, self_evaluation, peer_evaluations
                    ),
                }
            )

        return Response(
            {
                "metrics": {
                    "all": len(employees),
                    "to_do": todo_count,
                    "in_progress": in_progress_count,
                    "completed": completed_count,
                },
                "evaluations": results,
            }
        )


class ManagerEmployeeReviewView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManager,
    ]

    def get(self, request, employee_id):
        employee = get_object_or_404(User, id=employee_id, is_active=True)

        cycle = EvaluationCycle.objects.filter(
            status=EvaluationCycle.STATUS_OPEN
        ).first()
        if not cycle:
            cycle = EvaluationCycle.objects.order_by("-start_date", "-id").first()

        if not cycle:
            return Response(
                {"detail": "No evaluation cycle found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 1. Fetch Self Evaluation
        self_eval = Evaluation.objects.filter(
            cycle=cycle,
            evaluator=employee,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_SELF,
        ).first()

        # 2. Fetch Peer Evaluation with related evaluator user details
        peer_eval = (
            Evaluation.objects.filter(
                cycle=cycle,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_PEER,
            )
            .select_related("evaluator")
            .first()
        )

        # 3. Fallback: Check PeerAssignment if Evaluation record doesn't exist yet
        evaluator_user = None
        if peer_eval and peer_eval.evaluator:
            evaluator_user = peer_eval.evaluator
        else:
            peer_assignment = (
                PeerAssignment.objects.filter(cycle=cycle, evaluatee=employee)
                .select_related("evaluator")
                .first()
            )
            if peer_assignment:
                evaluator_user = peer_assignment.evaluator

        # Build evaluator response object (default to empty string structure if no evaluator exists)
        if evaluator_user:
            evaluator_info = {
                "id": evaluator_user.id,
                "first_name": evaluator_user.first_name or "",
                "last_name": evaluator_user.last_name or "",
                "designation": getattr(evaluator_user, "role", None)
                or getattr(evaluator_user, "designation", "")
                or "Evaluator",
            }
        else:
            evaluator_info = {
                "id": None,
                "first_name": "",
                "last_name": "",
                "designation": "",
            }

        # 4. Map answers by question_id
        self_answers_map = {}
        if self_eval:
            for ans in self_eval.answers.select_related(
                "question", "question__category"
            ).all():
                self_answers_map[ans.question_id] = ans

        peer_answers_map = {}
        if peer_eval:
            for ans in peer_eval.answers.select_related(
                "question", "question__category"
            ).all():
                peer_answers_map[ans.question_id] = ans

        all_question_ids = set(self_answers_map.keys()).union(
            set(peer_answers_map.keys())
        )

        # 5. Group questions into categories
        categories_dict = {}

        for q_id in all_question_ids:
            self_ans = self_answers_map.get(q_id)
            peer_ans = peer_answers_map.get(q_id)

            question_obj = (self_ans or peer_ans).question
            category_name = getattr(question_obj.category, "name", "General")

            question_data = {
                "question_id": question_obj.id,
                "question_text": question_obj.text,
                "self_score": self_ans.score if self_ans else 0,
                "peer_score": peer_ans.score if peer_ans else 0,
                "self_justification": self_ans.justification if self_ans else "",
                "peer_justification": peer_ans.justification if peer_ans else "",
            }

            if category_name not in categories_dict:
                categories_dict[category_name] = []

            categories_dict[category_name].append(question_data)

        categories_list = [
            {"category_name": category_name, "questions": questions}
            for category_name, questions in categories_dict.items()
        ]

        evaluatee_designation = (
            getattr(employee, "role", None)
            or getattr(employee, "designation", "")
            or "Developer"
        )

        return Response(
            {
                "evaluatee": {
                    "id": employee.id,
                    "first_name": employee.first_name or "",
                    "last_name": employee.last_name or "",
                    "designation": evaluatee_designation,
                },
                "evaluator": evaluator_info,  # <--- Evaluator object matching evaluatee shape
                "overall_score": getattr(peer_eval, "overall_score", 4.2),
                "submitted_on": peer_eval.updated_at.strftime("%d %B, %Y")
                if (peer_eval and peer_eval.updated_at)
                else None,
                "categories": categories_list,
            }
        )


class FinalReviewCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManager,
    ]

    def post(self, request, employee_id):
        employee = get_object_or_404(
            User,
            id=employee_id,
            is_active=True,
        )

        serializer = FinalReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self_eval_id = serializer.validated_data["self_eval_id"]
        justification = serializer.validated_data["justification"]

        try:
            self_evaluation = Evaluation.objects.get(
                id=self_eval_id,
                evaluator=employee,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_SELF,
            )
        except Evaluation.DoesNotExist:
            return Response(
                {"detail": "Self evaluation not found for this employee."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cycle = self_evaluation.cycle

        peer_evaluations = list(
            Evaluation.objects.filter(
                cycle=cycle,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_PEER,
            )
        )

        ready = _check_ready_for_final_review(cycle, employee, self_evaluation, peer_evaluations)

        if not ready:
            return Response(
                {
                    "detail": "Self and peer evaluations must all be locked before performing the final review."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        review = FinalReview.objects.create(
            manager=request.user,
            employee=employee,
            self_evaluation=self_evaluation,
            justification=justification,
            status=FinalReview.STATUS_COMPLETED,
        )

        return Response(
            FinalReviewSerializer(review).data,
            status=status.HTTP_201_CREATED,
        )