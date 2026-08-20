from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from questions.models import Question

from .models import Answer, Evaluation, EvaluationCycle, PeerAssignment
from .serializers import (
    AnswerSerializer,
    AvailableEmployeeSerializer,
    EvaluationCreateSerializer,
    EvaluationCycleSerializer,
    EvaluationDetailSerializer,
    EvaluationSerializer,
    PeerAssignmentCreateSerializer,
    PeerAssignmentSerializer,
    SaveAnswersSerializer,
)


class EvaluationCycleListView(ListAPIView):
    serializer_class = EvaluationCycleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = EvaluationCycle.objects.all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class AvailableEmployeesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")
        search = request.query_params.get("search", "")

        if not cycle_id:
            return Response(
                {"detail": "cycle_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not EvaluationCycle.objects.filter(pk=cycle_id).exists():
            return Response(
                {"detail": "Evaluation cycle not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        assigned_evaluatee_ids = PeerAssignment.objects.filter(
            cycle_id=cycle_id,
            evaluator=request.user,
        ).values_list("evaluatee_id", flat=True)

        employees = User.objects.filter(is_active=True).exclude(pk=request.user.pk)

        if search:
            employees = employees.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )

        results = []
        for employee in employees:
            results.append(
                {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "role": employee.role,
                    "availability": "available"
                    if employee.id not in assigned_evaluatee_ids
                    else "assigned",
                }
            )

        serializer = AvailableEmployeeSerializer(results, many=True)
        return Response(serializer.data)


class PeerAssignmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PeerAssignmentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        peer_assignment = serializer.save()
        return Response(
            PeerAssignmentSerializer(peer_assignment).data,
            status=status.HTTP_201_CREATED,
        )
class MyPeerAssignmentsView(ListAPIView):
    serializer_class = PeerAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            PeerAssignment.objects
            .filter(evaluator=self.request.user)
            .select_related("cycle", "evaluator", "evaluatee")
        )
class PeerAssignmentApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            assignment = PeerAssignment.objects.get(pk=pk)
        except PeerAssignment.DoesNotExist:
            return Response(
                {"detail": "Peer assignment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only the assigned evaluator can approve it
        if assignment.evaluator != request.user:
            return Response(
                {"detail": "You do not have permission to approve this assignment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Only pending assignments can be approved
        if assignment.status != PeerAssignment.STATUS_PENDING:
            return Response(
                {"detail": "Only pending assignments can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.status = PeerAssignment.STATUS_APPROVED
        assignment.save(update_fields=["status", "updated_at"])

        return Response(
            PeerAssignmentSerializer(assignment).data,
            status=status.HTTP_200_OK,
        )

class EvaluationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EvaluationCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        evaluation = serializer.save()
        return Response(
            EvaluationSerializer(evaluation).data,
            status=status.HTTP_201_CREATED,
        )


class EvaluationMineView(ListAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Evaluation.objects.filter(
            evaluator=self.request.user
        ).select_related(
            "cycle", "evaluator", "evaluatee", "peer_assignment"
        ).prefetch_related("answers")


class EvaluationDetailView(RetrieveAPIView):
    serializer_class = EvaluationDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Evaluation.objects.select_related(
            "cycle",
            "evaluator",
            "evaluatee",
            "peer_assignment",
        ).prefetch_related("answers__question")
        if user.is_staff:
            return qs
        return qs.filter(Q(evaluator=user) | Q(evaluatee=user))

    def patch(self, request, pk):
        return SaveAnswersView().patch(request, pk)


class SaveAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            evaluation = Evaluation.objects.get(pk=pk)
        except Evaluation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if evaluation.evaluator != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to edit this evaluation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if evaluation.status != Evaluation.STATUS_DRAFT:
            return Response(
                {"detail": "This evaluation is locked and cannot be edited."},
                status=status.HTTP_423_LOCKED,
            )

        serializer = SaveAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data["answers"]:
            question_id = item["question_id"]
            if not Question.objects.filter(pk=question_id).exists():
                return Response(
                    {"detail": f"Question {question_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            Answer.objects.update_or_create(
                evaluation=evaluation,
                question_id=question_id,
                defaults={
                    "score": item["score"],
                    "justification": item.get("justification"),
                },
            )

        evaluation.status = Evaluation.STATUS_DRAFT
        evaluation.save(update_fields=["status", "updated_at"])

        return Response(EvaluationSerializer(evaluation).data)


class AnswerDetailView(RetrieveAPIView):
    serializer_class = AnswerSerializer
    permission_classes = [IsAuthenticated]
    queryset = Answer.objects.select_related("evaluation", "question")


class SubmitEvaluationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            evaluation = Evaluation.objects.prefetch_related("answers").get(pk=pk)
        except Evaluation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if evaluation.evaluator != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to submit this evaluation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if evaluation.status not in (Evaluation.STATUS_DRAFT, Evaluation.STATUS_NOT_STARTED):
            return Response(
                {"detail": "This evaluation has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answers_by_question = {
            ans.question_id: ans for ans in evaluation.answers.all()
        }
        all_questions = Question.objects.all()

        # 1. Required questions check
        for question in all_questions:
            ans = answers_by_question.get(question.id)
            if ans is None or ans.score is None:
                return Response(
                    {"detail": f"Question {question.id} must be answered before submission."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 2. Score = 5 justification check
        for ans in evaluation.answers.all():
            if ans.score == 5 and (not ans.justification or not ans.justification.strip()):
                return Response(
                    {"detail": f"Question {ans.question_id} has a score of 5 and requires a written justification."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 3. Diff-2 rule check
        comp_eval = None
        if evaluation.evaluation_type == Evaluation.TYPE_PEER:
            comp_eval = Evaluation.objects.filter(
                cycle=evaluation.cycle,
                evaluatee=evaluation.evaluatee,
                evaluation_type=Evaluation.TYPE_SELF,
            ).first()
        elif evaluation.evaluation_type == Evaluation.TYPE_SELF:
            comp_eval = Evaluation.objects.filter(
                cycle=evaluation.cycle,
                evaluatee=evaluation.evaluatee,
                evaluation_type=Evaluation.TYPE_PEER,
            ).first()

        has_diff_2 = False
        if comp_eval:
            comp_answers = {ans.question_id: ans for ans in comp_eval.answers.all()}
            for ans in evaluation.answers.all():
                if ans.question_id in comp_answers:
                    comp_ans = comp_answers[ans.question_id]
                    if comp_ans.score is not None and abs(ans.score - comp_ans.score) >= 2:
                        has_diff_2 = True
                        if not ans.justification or not ans.justification.strip():
                            return Response(
                                {
                                    "detail": f"Score difference of 2 or more on question {ans.question_id} requires a written justification."
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

        if has_diff_2:
            evaluation.status = Evaluation.STATUS_DIFF_REVIEW
        else:
            evaluation.status = Evaluation.STATUS_SUBMITTED

        evaluation.submitted_at = timezone.now()
        evaluation.save(update_fields=["status", "submitted_at", "updated_at"])

        return Response(EvaluationSerializer(evaluation).data, status=status.HTTP_200_OK)
