from datetime import date
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.evaluations.models import Evaluation, EvaluationCycle

User = get_user_model()


class DashboardCountsTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            email="testuser@company.com",
            first_name="Test",
            last_name="User",
            is_staff=False,
        )
        self.user.set_password("pass12345")
        self.user.save()

        self.other_user = User.objects.create(
            email="other@company.com",
            first_name="Other",
            last_name="User",
            is_staff=False,
        )
        self.other_user.set_password("pass12345")
        self.other_user.save()

        self.cycle = EvaluationCycle.objects.create(
            name="Q3 2026",
            status=EvaluationCycle.STATUS_OPEN,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
        )

        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_case_1_submitted_2_locked_1_draft_1_diff_review_2_1(self):
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_SUBMITTED)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_SUBMITTED)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_LOCKED)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.user, evaluation_type=Evaluation.TYPE_SELF, status=Evaluation.STATUS_DRAFT)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_DIFF_REVIEW_2)

        res = self.client.get("/api/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["counts"]["in_progress"], 2)
        self.assertEqual(res.data["counts"]["completed"], 3)

    def test_case_2_submitted_0_locked_2(self):
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_LOCKED)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_LOCKED)

        res = self.client.get("/api/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["counts"]["completed"], 2)

    def test_case_3_submitted_2_locked_0(self):
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_SUBMITTED)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_SUBMITTED)

        res = self.client.get("/api/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["counts"]["completed"], 2)

    def test_case_4_diff_review_2_diff_review_2_1_draft_1(self):
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_DIFF_REVIEW)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_DIFF_REVIEW)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.other_user, evaluation_type=Evaluation.TYPE_PEER, status=Evaluation.STATUS_DIFF_REVIEW_2)
        Evaluation.objects.create(cycle=self.cycle, evaluator=self.user, evaluatee=self.user, evaluation_type=Evaluation.TYPE_SELF, status=Evaluation.STATUS_DRAFT)

        res = self.client.get("/api/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["counts"]["in_progress"], 4)
        self.assertEqual(res.data["counts"]["completed"], 0)
