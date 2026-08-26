import csv

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.evaluations.models import Evaluation
from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.evaluations.models import (
    Evaluation,
    EvaluationCycle,
)

from .serializers import (
    ReportListSerializer,
    ReportDetailSerializer,
)


class ReportExportView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        cycle_id = request.query_params.get(
            "cycle_id"
        )

        file_format = request.query_params.get(
            "format"
        )

        # ----------------------------------
        # Validate format
        # ----------------------------------

        if file_format != "csv":
            return HttpResponse(
                "Only CSV format is supported.",
                status=400,
            )

        # ----------------------------------
        # Validate cycle
        # ----------------------------------

        if not cycle_id:
            return HttpResponse(
                "cycle_id is required.",
                status=400,
            )

        # ----------------------------------
        # Get evaluations
        # ----------------------------------

        evaluations = Evaluation.objects.filter(
            cycle_id=cycle_id
        ).select_related(
            "evaluator",
            "evaluatee",
        ).prefetch_related(
            "answers__question__category"
        )

        # ----------------------------------
        # Create CSV response
        # ----------------------------------

        response = HttpResponse(
            content_type="text/csv"
        )

        response[
            "Content-Disposition"
        ] = 'attachment; filename="evaluation_report.csv"'

        writer = csv.writer(response)

        # ----------------------------------
        # CSV header
        # ----------------------------------

        writer.writerow([
            "employee",
            "evaluator",
            "evaluation_type",
            "category",
            "question",
            "score",
            "justification",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
        ])

        # ----------------------------------
        # CSV rows
        # ----------------------------------

        for evaluation in evaluations:

            employee_name = (
                f"{evaluation.evaluatee.first_name} "
                f"{evaluation.evaluatee.last_name}"
            )

            evaluator_name = (
                f"{evaluation.evaluator.first_name} "
                f"{evaluation.evaluator.last_name}"
            )

            for answer in evaluation.answers.all():

                writer.writerow([
                    employee_name,
                    evaluator_name,
                    evaluation.evaluation_type,
                    answer.question.category.name,
                    answer.question.text,
                    answer.score,
                    answer.justification,
                    evaluation.status,
                    evaluation.submitted_at,
                    evaluation.created_at,
                    evaluation.updated_at,
                ])

        return response

class ReportListView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        cycle_id = request.query_params.get(
            "cycle_id"
        )

        if not cycle_id:
            return Response(
                {
                    "detail": "cycle_id is required."
                },
                status=400,
            )

        # Get evaluations for this cycle
        evaluations = Evaluation.objects.filter(
            cycle_id=cycle_id
        ).select_related(
            "evaluator",
            "evaluatee",
        )

        reports = []

        for evaluation in evaluations:

            # Calculate overall score
            answers = evaluation.answers.all()

            if answers.exists():

                total_score = sum(
                    answer.score
                    for answer in answers
                )

                overall_score = round(
                    total_score / answers.count(),
                    2
                )

            else:
                overall_score = 0.0

            employee_name = (
                f"{evaluation.evaluatee.first_name} "
                f"{evaluation.evaluatee.last_name}"
            )

            evaluator_name = (
                f"{evaluation.evaluator.first_name} "
                f"{evaluation.evaluator.last_name}"
            )

            reports.append({
                "evaluation_id": evaluation.id,

                "employee": employee_name,

                "evaluating": evaluator_name,

                "status": evaluation.status,

                "overall_score": overall_score,
            })

        serializer = ReportListSerializer(
            reports,
            many=True,
        )

        return Response(serializer.data)

class ReportDetailView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, evaluation_id):

        # ----------------------------------
        # 1. Get peer evaluation
        # ----------------------------------

        peer_evaluation = get_object_or_404(
            Evaluation.objects.select_related(
                "evaluatee",
                "evaluator",
            ),
            id=evaluation_id,
            evaluation_type=Evaluation.TYPE_PEER,
        )

        employee = peer_evaluation.evaluatee
        evaluator = peer_evaluation.evaluator

        # ----------------------------------
        # 2. Find employee self evaluation
        # ----------------------------------

        self_evaluation = Evaluation.objects.filter(
            cycle=peer_evaluation.cycle,
            evaluator=employee,
            evaluatee=employee,
            evaluation_type=Evaluation.TYPE_SELF,
        ).first()

        # ----------------------------------
        # 3. Build self answer dictionary
        # ----------------------------------

        self_answers = {}

        if self_evaluation:

            for answer in self_evaluation.answers.select_related(
                "question",
                "question__category",
            ):

                self_answers[
                    answer.question_id
                ] = answer

        # ----------------------------------
        # 4. Build peer answer dictionary
        # ----------------------------------

        peer_answers = {}

        for answer in peer_evaluation.answers.select_related(
            "question",
            "question__category",
        ):

            peer_answers[
                answer.question_id
            ] = answer

        # ----------------------------------
        # 5. Get all questions
        # ----------------------------------

        question_ids = set(
            self_answers.keys()
        ) | set(
            peer_answers.keys()
        )

        # ----------------------------------
        # 6. Build categories
        # ----------------------------------

        categories = {}

        for question_id in question_ids:

            self_answer = self_answers.get(
                question_id
            )

            peer_answer = peer_answers.get(
                question_id
            )

            # Get question from either answer
            answer_reference = (
                peer_answer
                or self_answer
            )

            question = (
                answer_reference.question
            )

            category = question.category

            # Create category if needed
            if category.id not in categories:

                categories[category.id] = {
                    "name": category.name,
                    "questions": [],
                }

            # ----------------------------------
            # Scores
            # ----------------------------------

            self_score = (
                self_answer.score
                if self_answer
                else None
            )

            peer_score = (
                peer_answer.score
                if peer_answer
                else None
            )

            # ----------------------------------
            # Difference
            # ----------------------------------

            diff = None

            if (
                self_score is not None
                and peer_score is not None
            ):
                diff = abs(
                    self_score - peer_score
                )

            # ----------------------------------
            # Question result
            # ----------------------------------

            categories[
                category.id
            ]["questions"].append({

                "question_text":
                    question.text,

                "peer_score":
                    peer_score,

                "self_score":
                    self_score,

                "diff":
                    diff,

                "self_justification":
                    (
                        self_answer.justification
                        if self_answer
                        else None
                    ),

                "peer_justification":
                    (
                        peer_answer.justification
                        if peer_answer
                        else None
                    ),
            })

        # ----------------------------------
        # 7. Calculate overall peer score
        # ----------------------------------

        peer_answers_list = list(
            peer_answers.values()
        )

        if peer_answers_list:

            overall_score = round(
                sum(
                    answer.score
                    for answer in peer_answers_list
                )
                / len(peer_answers_list),
                2,
            )

        else:

            overall_score = 0.0

        # ----------------------------------
        # 8. Final response
        # ----------------------------------

        data = {

            "evaluatee": {
                "id": employee.id,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "role": employee.designation,
            },

            "evaluator": {
                "id": evaluator.id,
                "first_name": evaluator.first_name,
                "last_name": evaluator.last_name,
            },

            "status": peer_evaluation.status,

            "overall_score": overall_score,

            "categories": list(
                categories.values()
            ),
        }

        serializer = ReportDetailSerializer(
            data
        )

        return Response(
            serializer.data
        )