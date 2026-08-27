import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evaluations.models import Evaluation, EvaluationCycle
from .serializers import (
    ReportDetailSerializer,
    ReportListSerializer,
)


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")
        file_format = request.query_params.get("format")

        if file_format != "csv":
            return Response(
                {"detail": "Only CSV format is supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not cycle_id:
            return Response(
                {"detail": "cycle_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cycle_id_int = int(cycle_id)
            if not EvaluationCycle.objects.filter(id=cycle_id_int).exists():
                return Response(
                    {"detail": "Evaluation cycle not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except ValueError:
            return Response(
                {"detail": "Invalid cycle_id format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evaluations = Evaluation.objects.filter(
            cycle_id=cycle_id_int
        ).select_related(
            "evaluator",
            "evaluatee",
        ).prefetch_related(
            "answers__question__category"
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="evaluation_report.csv"'

        writer = csv.writer(response)

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

        for evaluation in evaluations:
            employee_name = f"{evaluation.evaluatee.first_name} {evaluation.evaluatee.last_name}".strip()
            evaluator_name = f"{evaluation.evaluator.first_name} {evaluation.evaluator.last_name}".strip()

            for answer in evaluation.answers.all():
                submitted_at_str = evaluation.submitted_at.isoformat() if evaluation.submitted_at else ""
                created_at_str = evaluation.created_at.isoformat() if evaluation.created_at else ""
                updated_at_str = evaluation.updated_at.isoformat() if evaluation.updated_at else ""

                writer.writerow([
                    employee_name,
                    evaluator_name,
                    evaluation.evaluation_type,
                    answer.question.category.name,
                    answer.question.text,
                    answer.score,
                    answer.justification or "",
                    evaluation.status,
                    submitted_at_str,
                    created_at_str,
                    updated_at_str,
                ])

        return response


class ReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle_id = request.query_params.get("cycle_id")

        if not cycle_id:
            return Response(
                {"detail": "cycle_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cycle_id_int = int(cycle_id)
            if not EvaluationCycle.objects.filter(id=cycle_id_int).exists():
                return Response(
                    {"detail": "Evaluation cycle not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except ValueError:
            return Response(
                {"detail": "Invalid cycle_id format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evaluations = Evaluation.objects.filter(
            cycle_id=cycle_id_int
        ).select_related(
            "evaluator",
            "evaluatee",
        ).prefetch_related("answers")

        reports = []

        for evaluation in evaluations:
            answers = evaluation.answers.all()

            if answers.exists():
                total_score = sum(answer.score for answer in answers)
                overall_score = round(total_score / answers.count(), 2)
            else:
                overall_score = 0.0

            employee_name = f"{evaluation.evaluatee.first_name} {evaluation.evaluatee.last_name}".strip()
            evaluator_name = f"{evaluation.evaluator.first_name} {evaluation.evaluator.last_name}".strip()

            reports.append({
                "evaluation_id": evaluation.id,
                "employee": employee_name,
                "evaluating": evaluator_name,
                "status": evaluation.status,
                "overall_score": overall_score,
            })

        serializer = ReportListSerializer(reports, many=True)
        return Response(serializer.data)


class ReportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, evaluation_id):
        evaluation = get_object_or_404(
            Evaluation.objects.select_related(
                "evaluatee",
                "evaluator",
                "cycle",
            ),
            id=evaluation_id,
        )

        employee = evaluation.evaluatee
        cycle = evaluation.cycle

        if evaluation.evaluation_type == Evaluation.TYPE_PEER:
            peer_evaluation = evaluation
            evaluator = peer_evaluation.evaluator
            self_evaluation = Evaluation.objects.filter(
                cycle=cycle,
                evaluator=employee,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_SELF,
            ).first()
        else:
            self_evaluation = evaluation
            peer_evaluation = Evaluation.objects.filter(
                cycle=cycle,
                evaluatee=employee,
                evaluation_type=Evaluation.TYPE_PEER,
            ).select_related("evaluator").first()
            evaluator = peer_evaluation.evaluator if peer_evaluation else evaluation.evaluator

        self_answers = {}
        if self_evaluation:
            for answer in self_evaluation.answers.select_related(
                "question",
                "question__category",
            ):
                self_answers[answer.question_id] = answer

        peer_answers = {}
        if peer_evaluation:
            for answer in peer_evaluation.answers.select_related(
                "question",
                "question__category",
            ):
                peer_answers[answer.question_id] = answer

        question_ids = set(self_answers.keys()) | set(peer_answers.keys())

        categories_dict = {}

        for question_id in question_ids:
            self_answer = self_answers.get(question_id)
            peer_answer = peer_answers.get(question_id)
            answer_reference = peer_answer or self_answer

            if not answer_reference:
                continue

            question = answer_reference.question
            category = question.category

            if category.id not in categories_dict:
                categories_dict[category.id] = {
                    "name": category.name,
                    "order": getattr(category, "order", 0),
                    "questions": [],
                }

            self_score = self_answer.score if self_answer else None
            peer_score = peer_answer.score if peer_answer else None

            diff = None
            if self_score is not None and peer_score is not None:
                diff = abs(self_score - peer_score)

            categories_dict[category.id]["questions"].append({
                "question_text": question.text,
                "peer_score": peer_score,
                "self_score": self_score,
                "diff": diff,
                "self_justification": self_answer.justification if self_answer else None,
                "peer_justification": peer_answer.justification if peer_answer else None,
            })

        target_answers = list(peer_answers.values()) if peer_answers else list(self_answers.values())

        if target_answers:
            overall_score = round(
                sum(answer.score for answer in target_answers) / len(target_answers),
                2,
            )
        else:
            overall_score = 0.0

        role_name = getattr(employee, "designation", None) or getattr(employee, "role", "")

        sorted_categories = sorted(
            categories_dict.values(),
            key=lambda c: (c["order"], c["name"])
        )
        for cat_data in sorted_categories:
            cat_data.pop("order", None)

        data = {
            "evaluatee": {
                "id": employee.id,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "role": role_name,
            },
            "evaluator": {
                "id": evaluator.id,
                "first_name": evaluator.first_name,
                "last_name": evaluator.last_name,
            },
            "status": evaluation.status,
            "overall_score": overall_score,
            "categories": sorted_categories,
        }

        serializer = ReportDetailSerializer(data)
        return Response(serializer.data)