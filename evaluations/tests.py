from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from evaluations.models import Answer, Evaluation, EvaluationCycle, PeerAssignment
from questions.models import Category, Question

User = get_user_model()


class EvaluationsAPITestCase(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="usera",
            email="usera@example.com",
            password="pass12345",
            first_name="User",
            last_name="A",
        )
        self.user_b = User.objects.create_user(
            username="userb",
            email="userb@example.com",
            password="pass12345",
            first_name="User",
            last_name="B",
        )

        self.cycle = EvaluationCycle.objects.create(
            name="Q3 2026",
            status=EvaluationCycle.STATUS_OPEN,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
        )

        self.category = Category.objects.create(name="Technical Skills", order=1)
        self.question1 = Question.objects.create(
            category=self.category,
            text="Question 1 text",
            order=1,
        )
        self.question2 = Question.objects.create(
            category=self.category,
            text="Question 2 text",
            order=2,
        )

        self.authenticate(self.user_a)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_submitted_evaluation_rejects_further_patch_attempts(self):
        """TEST 1 — Submitted evaluation rejects further PATCH/write attempts"""
        evaluation = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_a,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        # Add initial answer
        Answer.objects.create(
            evaluation=evaluation,
            question=self.question1,
            score=3,
            justification="Initial justification",
        )
        Answer.objects.create(
            evaluation=evaluation,
            question=self.question2,
            score=3,
            justification="Initial justification",
        )

        # Submit evaluation
        submit_res = self.client.post(f"/evaluations/{evaluation.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
        evaluation.refresh_from_db()
        self.assertIn(evaluation.status, (Evaluation.STATUS_SUBMITTED, Evaluation.STATUS_LOCKED))

        # Attempt PATCH to direct evaluation endpoint
        patch_res1 = self.client.patch(
            f"/evaluations/{evaluation.id}/",
            {
                "answers": [
                    {
                        "question_id": self.question1.id,
                        "score": 4,
                        "justification": "Attempted update",
                    }
                ]
            },
            format="json",
        )
        self.assertIn(patch_res1.status_code, (status.HTTP_423_LOCKED, status.HTTP_400_BAD_REQUEST))

        # Attempt PATCH to answers endpoint
        patch_res2 = self.client.patch(
            f"/evaluations/{evaluation.id}/answers/",
            {
                "answers": [
                    {
                        "question_id": self.question1.id,
                        "score": 4,
                        "justification": "Attempted update",
                    }
                ]
            },
            format="json",
        )
        self.assertIn(patch_res2.status_code, (status.HTTP_423_LOCKED, status.HTTP_400_BAD_REQUEST))

        # Assert evaluation answers remain unchanged
        ans1 = Answer.objects.get(evaluation=evaluation, question=self.question1)
        self.assertEqual(ans1.score, 3)
        self.assertEqual(ans1.justification, "Initial justification")

    def test_score_5_without_justification_rejected_on_submit(self):
        """TEST 2 — Score = 5 without justification is rejected on submit"""
        evaluation = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_a,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        Answer.objects.create(
            evaluation=evaluation,
            question=self.question1,
            score=5,
            justification=None,  # Missing justification for score 5
        )
        Answer.objects.create(
            evaluation=evaluation,
            question=self.question2,
            score=3,
            justification="Normal score",
        )

        # Attempt submit
        submit_res = self.client.post(f"/evaluations/{evaluation.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Assert evaluation remains a draft
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, Evaluation.STATUS_DRAFT)

    def test_diff_2_rule_rejected_when_justification_missing(self):
        """TEST 3 — Diff-2 rule rejected on submit when required justification is missing"""
        # Create self evaluation for User B with score 1
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_SUBMITTED,
        )
        Answer.objects.create(
            evaluation=self_eval,
            question=self.question1,
            score=1,
            justification="Self score 1",
        )
        Answer.objects.create(
            evaluation=self_eval,
            question=self.question2,
            score=1,
            justification="Self score 1",
        )

        # Create peer evaluation by User A for User B with peer score 4 (|4 - 1| = 3 >= 2)
        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )

        # Peer answer has score=4 (diff=3 >= 2) but NO justification
        peer_ans1 = Answer.objects.create(
            evaluation=peer_eval,
            question=self.question1,
            score=4,
            justification="",  # Missing justification for Diff-2
        )
        Answer.objects.create(
            evaluation=peer_eval,
            question=self.question2,
            score=1,
            justification="No diff",
        )

        # Attempt submit peer evaluation -> must be rejected because justification missing for diff >= 2
        submit_res = self.client.post(f"/evaluations/{peer_eval.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_400_BAD_REQUEST)
        peer_eval.refresh_from_db()
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DRAFT)

        # Now provide the required justification and attempt submit again -> should succeed and set status to diff-review
        peer_ans1.justification = "Detailed justification for high score difference"
        peer_ans1.save()

        submit_res2 = self.client.post(f"/evaluations/{peer_eval.id}/submit/")
        self.assertEqual(submit_res2.status_code, status.HTTP_200_OK)
        peer_eval.refresh_from_db()
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DIFF_REVIEW)

    def test_draft_save_allowed_when_incomplete(self):
        """TEST 4 — Draft save is allowed even when answers are incomplete"""
        evaluation = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_a,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        # Save an incomplete draft: score = 5 with NO justification, and question 2 not answered at all
        patch_res = self.client.patch(
            f"/evaluations/{evaluation.id}/answers/",
            {
                "answers": [
                    {
                        "question_id": self.question1.id,
                        "score": 5,
                        "justification": None,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        # Assert evaluation remains editable / draft
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, Evaluation.STATUS_DRAFT)

        # Confirm answer score 5 saved with justification None
        ans1 = Answer.objects.get(evaluation=evaluation, question=self.question1)
        self.assertEqual(ans1.score, 5)
        self.assertIsNone(ans1.justification)
