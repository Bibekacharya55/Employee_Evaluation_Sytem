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
            return Response([])

        evaluatee_ids = set(
            Evaluation.objects.filter(cycle=cycle).values_list("evaluatee_id", flat=True)
        ).union(
            PeerAssignment.objects.filter(cycle=cycle).values_list("evaluatee_id", flat=True)
        )

        if evaluatee_ids:
            employees = User.objects.filter(id__in=evaluatee_ids, is_active=True).order_by("id")
        else:
            employees = User.objects.filter(is_active=True).order_by("id")

        results = []
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
                )
            )

            self_status = self_evaluation.status if self_evaluation else "not_started"
            peer_statuses = [pe.status for pe in peer_evaluations]

            ready = _check_ready_for_final_review(cycle, employee, self_evaluation, peer_evaluations)

            results.append({
                "employee": {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                },
                "self_evaluation_status": self_status,
                "peer_evaluation_statuses": peer_statuses,
                "ready_for_final_review": ready,
            })

        return Response(results)


class ManagerEmployeeReviewView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsManager,
    ]

    def get(self, request, employee_id):
        employee = get_object_or_404(
            User,
            id=employee_id,
            is_active=True,
        )

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
            ).select_related("evaluator", "evaluatee")
        )

        ready = _check_ready_for_final_review(cycle, employee, self_evaluation, peer_evaluations)

        self_data = None
        if self_evaluation:
            self_data = EvaluationDetailSerializer(self_evaluation).data

        peer_data = EvaluationDetailSerializer(peer_evaluations, many=True).data

        username_val = getattr(employee, "username", None) or employee.email

        employee_data = {
            "id": employee.id,
            "username": username_val,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
        }

        return Response({
            "employee": employee_data,
            "ready_for_final_review": ready,
            "self_evaluation": self_data,
            "peer_evaluations": peer_data,
        })


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
        comments = serializer.validated_data["comments"]

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
            comments=comments,
            status=FinalReview.STATUS_COMPLETED,
        )

        return Response(
            FinalReviewSerializer(review).data,
            status=status.HTTP_201_CREATED,
        )