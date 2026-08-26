from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.evaluations.models import Evaluation, EvaluationCycle
from apps.evaluations.serializers import EvaluationDetailSerializer

from .models import FinalReview
from .permissions import IsManager
from .serializers import (
    FinalReviewCreateSerializer,
    FinalReviewSerializer,
)


class ManagerEmployeeReviewView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsManager,
    ]

    def get(self, request, employee_id):

        # 1. Find employee
        employee = get_object_or_404(
            User,
            id=employee_id,
            is_active=True,
        )

        # 2. Find current open cycle
        cycle = EvaluationCycle.objects.filter(
            status=EvaluationCycle.STATUS_OPEN
        ).first()

        if not cycle:
            return Response(
                {
                    "detail": "No open evaluation cycle."
                },
                status=404,
            )

        # 3. Find employee's self evaluation
        self_evaluation = Evaluation.objects.filter(
            cycle=cycle,
            evaluator=employee,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_SELF,
        ).first()

        # 4. Find peer evaluations about this employee
        peer_evaluations = Evaluation.objects.filter(
            cycle=cycle,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_PEER,
        ).select_related(
            "evaluator",
            "evaluatee",
        )

        # 5. Check whether everything is locked
        ready_for_final_review = (
            self_evaluation is not None
            and self_evaluation.status == Evaluation.STATUS_LOCKED
            and not peer_evaluations.exclude(
                status=Evaluation.STATUS_LOCKED
            ).exists()
        )

        # 6. Serialize self evaluation
        self_data = None

        if self_evaluation:
            self_data = EvaluationDetailSerializer(
                self_evaluation
            ).data

        # 7. Serialize peer evaluations
        peer_data = EvaluationDetailSerializer(
            peer_evaluations,
            many=True,
        ).data

        # 8. Employee information
        employee_data = {
            "id": employee.id,
            "username": employee.email,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
        }

        # 9. Final response
        return Response({
            "employee": employee_data,
            "ready_for_final_review": ready_for_final_review,
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

        serializer = FinalReviewCreateSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        self_eval_id = serializer.validated_data[
            "self_eval_id"
        ]

        comments = serializer.validated_data[
            "comments"
        ]

        # Find the employee's self evaluation
        self_evaluation = get_object_or_404(
            Evaluation,
            id=self_eval_id,
            cycle__status=EvaluationCycle.STATUS_OPEN,
            evaluator=employee,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_SELF,
        )

        # Self evaluation must be locked
        if self_evaluation.status != Evaluation.STATUS_LOCKED:

            return Response(
                {
                    "detail": (
                        "Self and peer evaluations must "
                        "all be locked before performing "
                        "the final review."
                    )
                },
                status=400,
            )

        # Get all peer evaluations for employee
        peer_evaluations = Evaluation.objects.filter(
            cycle=self_evaluation.cycle,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_PEER,
        )

        # Every peer evaluation must be locked
        if peer_evaluations.exclude(
            status=Evaluation.STATUS_LOCKED
        ).exists():

            return Response(
                {
                    "detail": (
                        "Self and peer evaluations must "
                        "all be locked before performing "
                        "the final review."
                    )
                },
                status=400,
            )

        # Create final review
        review = FinalReview.objects.create(
            manager=request.user,
            employee=employee,
            self_evaluation=self_evaluation,
            comments=comments,
            status=FinalReview.STATUS_COMPLETED,
        )

        return Response(
            FinalReviewSerializer(review).data,
            status=201,
        )