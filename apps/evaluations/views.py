from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.questions.models import Category, Question

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
    SaveCategoryAnswersSerializer,
    ScoreCheckSerializer,
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
                    "designation": employee.designation,
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


def update_evaluation_answers(evaluation_id, user, data):
    try:
        evaluation = Evaluation.objects.get(pk=evaluation_id)
    except Evaluation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if evaluation.evaluator != user and not user.is_staff:
        return Response(
            {"detail": "You do not have permission to edit this evaluation."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if evaluation.status != Evaluation.STATUS_DRAFT:
        return Response(
            {"detail": "This evaluation is locked and cannot be edited."},
            status=status.HTTP_423_LOCKED,
        )

    serializer = SaveAnswersSerializer(data=data)
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
        return update_evaluation_answers(pk, request.user, request.data)


class SaveAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        return update_evaluation_answers(pk, request.user, request.data)


class SaveCategoryAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, category_id=None):
        try:
            evaluation = Evaluation.objects.get(pk=pk)
        except Evaluation.DoesNotExist:
            return Response(
                {"detail": "Evaluation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

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

        serializer = SaveCategoryAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_category_id = category_id or serializer.validated_data.get("category_id")
        if not target_category_id:
            return Response(
                {"detail": "Category ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not Category.objects.filter(pk=target_category_id).exists():
            return Response(
                {"detail": f"Category {target_category_id} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_answers = []
        for item in serializer.validated_data["answers"]:
            question_id = item["question_id"]
            score = item["score"]
            justification = item.get("justification")

            try:
                question = Question.objects.get(pk=question_id)
            except Question.DoesNotExist:
                return Response(
                    {"detail": f"Question {question_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if question.category_id != target_category_id:
                return Response(
                    {
                        "detail": f"Question {question_id} does not belong to category {target_category_id}."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            answer, created = Answer.objects.update_or_create(
                evaluation=evaluation,
                question=question,
                defaults={
                    "score": score,
                    "justification": justification,
                },
            )

            saved_answers.append(
                {
                    "questionId": question.id,
                    "score": answer.score,
                    "justification": answer.justification,
                }
            )

        evaluation.status = Evaluation.STATUS_DRAFT
        evaluation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "categoryId": target_category_id,
                "answers": saved_answers,
            },
            status=status.HTTP_200_OK,
        )


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

        # Mark current evaluation as SUBMITTED
        evaluation.status = Evaluation.STATUS_SUBMITTED
        evaluation.submitted_at = timezone.now()
        evaluation.save(update_fields=["status", "submitted_at", "updated_at"])

        # 3. Diff-2 rule check (ONLY if BOTH evaluations are submitted)
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

        # Score comparison happens ONLY when BOTH evaluations are submitted
        if comp_eval and comp_eval.status in (Evaluation.STATUS_SUBMITTED, Evaluation.STATUS_DIFF_REVIEW, Evaluation.STATUS_LOCKED):
            peer_eval = evaluation if evaluation.evaluation_type == Evaluation.TYPE_PEER else comp_eval
            self_eval = evaluation if evaluation.evaluation_type == Evaluation.TYPE_SELF else comp_eval

            peer_answers = {ans.question_id: ans for ans in peer_eval.answers.all()}
            self_answers = {ans.question_id: ans for ans in self_eval.answers.all()}

            has_diff_2 = False
            for q_id, p_ans in peer_answers.items():
                if q_id in self_answers:
                    s_ans = self_answers[q_id]
                    if p_ans.score is not None and s_ans.score is not None:
                        if abs(p_ans.score - s_ans.score) >= 2:
                            has_diff_2 = True
                            break

            if has_diff_2:
                peer_eval.status = Evaluation.STATUS_DIFF_REVIEW
                peer_eval.save(update_fields=["status", "updated_at"])
                self_eval.status = Evaluation.STATUS_DIFF_REVIEW
                self_eval.save(update_fields=["status", "updated_at"])
                evaluation.refresh_from_db()

        return Response(EvaluationSerializer(evaluation).data, status=status.HTTP_200_OK)


class ScoreCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            evaluation = Evaluation.objects.select_related(
                "cycle", "evaluator", "evaluatee"
            ).prefetch_related("answers__question").get(pk=pk)
        except Evaluation.DoesNotExist:
            return Response(
                {"detail": "Evaluation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if (
            evaluation.evaluator != request.user
            and evaluation.evaluatee != request.user
            and not request.user.is_staff
        ):
            return Response(
                {"detail": "You do not have permission to perform score check on this evaluation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Counterpart evaluation lookup
        comp_eval = Evaluation.objects.filter(
            cycle=evaluation.cycle,
            evaluatee=evaluation.evaluatee,
            evaluation_type=(
                Evaluation.TYPE_SELF
                if evaluation.evaluation_type == Evaluation.TYPE_PEER
                else Evaluation.TYPE_PEER
            ),
        ).prefetch_related("answers__question").first()

        # Map your_eval and counterpart_eval based on authenticated user
        if evaluation.evaluator == request.user:
            your_eval = evaluation
            counterpart_eval = comp_eval
        elif evaluation.evaluatee == request.user:
            your_eval = comp_eval
            counterpart_eval = evaluation
        else:
            your_eval = evaluation
            counterpart_eval = comp_eval

        your_answers = (
            {ans.question_id: ans for ans in your_eval.answers.all()}
            if your_eval
            else {}
        )
        counterpart_answers = (
            {ans.question_id: ans for ans in counterpart_eval.answers.all()}
            if counterpart_eval
            else {}
        )

        evaluatee = evaluation.evaluatee
        evaluatee_data = {
            "id": evaluatee.id,
            "first_name": evaluatee.first_name,
            "last_name": evaluatee.last_name,
            "designation": evaluatee.designation or "",
        }

        categories_dict = {}
        for category in Category.objects.prefetch_related("questions").all():
            cat_questions = []
            for question in category.questions.all():
                y_ans = your_answers.get(question.id)
                c_ans = counterpart_answers.get(question.id)

                y_score = y_ans.score if y_ans else None
                c_score = c_ans.score if c_ans else None

                if y_score is not None and c_score is not None:
                    diff = abs(y_score - c_score)
                else:
                    diff = 0

                if diff >= 2:
                    y_just = (
                        y_ans.justification.strip()
                        if (y_ans and y_ans.justification and y_ans.justification.strip())
                        else None
                    )
                    c_just = (
                        c_ans.justification.strip()
                        if (c_ans and c_ans.justification and c_ans.justification.strip())
                        else None
                    )

                    cat_questions.append(
                        {
                            "question_id": question.id,
                            "question_text": question.text,
                            "your_score": y_score,
                            "counterpart_score": c_score,
                            "difference": diff,
                            "your_justification": y_just,
                            "counterpart_justification": c_just,
                        }
                    )

            if cat_questions:
                categories_dict[category.id] = {
                    "category_id": category.id,
                    "category_name": category.name,
                    "questions": cat_questions,
                }

        remaining_count = 0
        for cat_data in categories_dict.values():
            for q_item in cat_data["questions"]:
                if q_item["your_justification"] is None:
                    remaining_count += 1

        return Response(
            {
                "evaluation_id": your_eval.id if your_eval else evaluation.id,
                "counterpart_evaluation_id": counterpart_eval.id if counterpart_eval else None,
                "evaluatee": evaluatee_data,
                "remaining_count": remaining_count,
                "categories": list(categories_dict.values()),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, pk):
        try:
            evaluation = Evaluation.objects.prefetch_related("answers").get(pk=pk)
        except Evaluation.DoesNotExist:
            return Response(
                {"detail": "Evaluation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if evaluation.evaluator != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to perform score check on this evaluation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if evaluation.status == Evaluation.STATUS_LOCKED:
            return Response(
                {"detail": "This evaluation is locked and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evaluation.status != Evaluation.STATUS_DIFF_REVIEW:
            return Response(
                {"detail": "Evaluation is not in diff-review status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Counterpart evaluation lookup
        comp_eval = Evaluation.objects.filter(
            cycle=evaluation.cycle,
            evaluatee=evaluation.evaluatee,
            evaluation_type=Evaluation.TYPE_SELF if evaluation.evaluation_type == Evaluation.TYPE_PEER else Evaluation.TYPE_PEER,
        ).first()

        if not comp_eval or comp_eval.status in (Evaluation.STATUS_DRAFT, Evaluation.STATUS_NOT_STARTED):
            return Response(
                {"detail": "Counterpart evaluation has not been submitted yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Determine required questions (abs(self_score - peer_score) >= 2)
        peer_eval = evaluation if evaluation.evaluation_type == Evaluation.TYPE_PEER else comp_eval
        self_eval = comp_eval if evaluation.evaluation_type == Evaluation.TYPE_PEER else evaluation

        peer_answers = {ans.question_id: ans for ans in peer_eval.answers.all()}
        self_answers = {ans.question_id: ans for ans in self_eval.answers.all()}

        required_question_ids = set()
        for q_id, p_ans in peer_answers.items():
            if q_id in self_answers:
                s_ans = self_answers[q_id]
                if p_ans.score is not None and s_ans.score is not None:
                    if abs(p_ans.score - s_ans.score) >= 2:
                        required_question_ids.add(q_id)

        # Check if current user has already completed all required score check justifications
        current_user_answers = {ans.question_id: ans for ans in evaluation.answers.all()}
        current_user_missing_count = 0
        for q_id in required_question_ids:
            ans = current_user_answers.get(q_id)
            if not ans or not ans.justification or not ans.justification.strip():
                current_user_missing_count += 1

        if current_user_missing_count == 0 and len(required_question_ids) > 0:
            return Response(
                {"detail": "Score check justifications have already been completed for this evaluation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ScoreCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        justifications_input = serializer.validated_data["justifications"]

        # Validate submitted question_ids and non-empty justifications
        for item in justifications_input:
            q_id = item["question_id"]
            just = item["justification"]
            if q_id not in required_question_ids:
                return Response(
                    {"detail": f"Question {q_id} does not require score check justification."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not just or not just.strip():
                return Response(
                    {"detail": f"Justification for question {q_id} cannot be empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Save justifications into existing Answer.justification
        for item in justifications_input:
            q_id = item["question_id"]
            just = item["justification"].strip()
            answer = Answer.objects.filter(evaluation=evaluation, question_id=q_id).first()
            if answer:
                answer.justification = just
                answer.save(update_fields=["justification", "updated_at"])

        # Re-fetch evaluation answers to compute remaining_count accurately
        evaluation.refresh_from_db()
        current_answers = {ans.question_id: ans for ans in evaluation.answers.all()}

        remaining_count = 0
        for q_id in required_question_ids:
            ans = current_answers.get(q_id)
            if not ans or not ans.justification or not ans.justification.strip():
                remaining_count += 1

        # Check if counterpart has any pending score check work
        counterpart_pending = False
        comp_answers = {ans.question_id: ans for ans in comp_eval.answers.all()}
        for q_id in required_question_ids:
            ans = comp_answers.get(q_id)
            if not ans or not ans.justification or not ans.justification.strip():
                counterpart_pending = True
                break

        if remaining_count == 0 and not counterpart_pending:
            evaluation.status = Evaluation.STATUS_LOCKED
            evaluation.save(update_fields=["status", "updated_at"])
            comp_eval.status = Evaluation.STATUS_LOCKED
            comp_eval.save(update_fields=["status", "updated_at"])

            return Response(
                {
                    "id": evaluation.id,
                    "status": Evaluation.STATUS_LOCKED,
                    "counterpart_status": Evaluation.STATUS_LOCKED,
                    "remaining_count": 0,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "id": evaluation.id,
                "status": Evaluation.STATUS_DIFF_REVIEW,
                "remaining_count": remaining_count,
            },
            status=status.HTTP_200_OK,
        )

