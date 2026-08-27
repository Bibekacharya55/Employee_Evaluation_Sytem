from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.evaluations.models import Answer, Evaluation, EvaluationCycle, PeerAssignment
from apps.questions.models import Category, Question

User = get_user_model()


class EvaluationsAPITestCase(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create(
            email="usera@example.com",
            first_name="User",
            last_name="A",
        )
        self.user_a.set_password("pass12345")
        self.user_a.save()

        self.user_b = User.objects.create(
            email="userb@example.com",
            first_name="User",
            last_name="B",
        )
        self.user_b.set_password("pass12345")
        self.user_b.save()

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
        """Submitted evaluation rejects further PATCH/write attempts"""
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
        submit_res = self.client.post(f"/api/evaluations/{evaluation.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)
        evaluation.refresh_from_db()
        self.assertIn(evaluation.status, (Evaluation.STATUS_SUBMITTED, Evaluation.STATUS_LOCKED))

        # Attempt PATCH to direct evaluation endpoint
        patch_res1 = self.client.patch(
            f"/api/evaluations/{evaluation.id}/",
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
            f"/api/evaluations/{evaluation.id}/answers/",
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
        """Score = 5 without justification is rejected on submit"""
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
            justification=None,
        )
        Answer.objects.create(
            evaluation=evaluation,
            question=self.question2,
            score=3,
            justification="Normal score",
        )

        submit_res = self.client.post(f"/api/evaluations/{evaluation.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_400_BAD_REQUEST)

        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, Evaluation.STATUS_DRAFT)

    def test_draft_save_allowed_when_incomplete(self):
        """Draft save is allowed even when answers are incomplete"""
        evaluation = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_a,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        patch_res = self.client.patch(
            f"/api/evaluations/{evaluation.id}/answers/",
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

        evaluation.refresh_from_db()
        self.assertEqual(evaluation.status, Evaluation.STATUS_DRAFT)

        ans1 = Answer.objects.get(evaluation=evaluation, question=self.question1)
        self.assertEqual(ans1.score, 5)
        self.assertIsNone(ans1.justification)

    def test_category_level_answer_saving(self):
        """Category-level answer saving and editing"""
        cat2 = Category.objects.create(name="Communication Skills", order=2)
        question3 = Question.objects.create(
            category=cat2,
            text="Question 3 text",
            order=1,
        )

        evaluation = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_a,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        url_cat1 = f"/api/evaluations/{evaluation.id}/categories/{self.category.id}/answers/"
        cat1_payload = {
            "categoryId": self.category.id,
            "answers": [
                {"questionId": self.question1.id, "score": 2},
                {"questionId": self.question2.id, "score": 3},
            ],
        }
        res1 = self.client.patch(url_cat1, cat1_payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["categoryId"], self.category.id)
        self.assertEqual(len(res1.data["answers"]), 2)

        # Edit Category 1 answers
        edit_cat1_payload = {
            "categoryId": self.category.id,
            "answers": [
                {"questionId": self.question1.id, "score": 5},
                {"questionId": self.question2.id, "score": 3},
            ],
        }
        res3 = self.client.patch(url_cat1, edit_cat1_payload, format="json")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Answer.objects.filter(evaluation=evaluation, question=self.question1).get().score, 5
        )

        # Verify invalid question/category combination rejected
        invalid_payload = {
            "categoryId": self.category.id,
            "answers": [
                {"questionId": question3.id, "score": 4},
            ],
        }
        res_invalid = self.client.patch(url_cat1, invalid_payload, format="json")
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # SCORE CHECK BUSINESS LOGIC SPECIFIC TESTS (TEST 1 to TEST 10)
    # -------------------------------------------------------------------------

    def test_1_only_one_side_submitted(self):
        """Test 1: Self submitted, Peer in DRAFT -> No score comparison, no Score Check"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=4)

        # Self submits
        self.authenticate(self.user_b)
        submit_res = self.client.post(f"/api/evaluations/{self_eval.id}/submit/")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()

        self.assertEqual(self_eval.status, Evaluation.STATUS_SUBMITTED)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DRAFT)

    def test_2_both_submitted_difference_1(self):
        """Test 2: Both submitted, difference = 1 -> No Score Check required"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=3)
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=3)

        # Submit Self then Peer
        self.authenticate(self.user_b)
        self.client.post(f"/api/evaluations/{self_eval.id}/submit/")

        self.authenticate(self.user_a)
        self.client.post(f"/api/evaluations/{peer_eval.id}/submit/")

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()

        self.assertEqual(self_eval.status, Evaluation.STATUS_SUBMITTED)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_SUBMITTED)

    def test_3_both_submitted_difference_2(self):
        """Test 3: Both submitted, difference = 2 -> BOTH Self and Peer enter diff-review"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)  # diff = 2
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=2)  # diff = 0

        self.authenticate(self.user_b)
        self.client.post(f"/api/evaluations/{self_eval.id}/submit/")

        self.authenticate(self.user_a)
        self.client.post(f"/api/evaluations/{peer_eval.id}/submit/")

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()

        self.assertEqual(self_eval.status, Evaluation.STATUS_DIFF_REVIEW)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DIFF_REVIEW)

    def test_4_both_submitted_difference_greater_than_2(self):
        """Test 4: Both submitted, difference > 2 -> BOTH Self and Peer enter diff-review"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=1)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=5, justification="High score")  # diff = 4
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=2)

        self.authenticate(self.user_b)
        self.client.post(f"/api/evaluations/{self_eval.id}/submit/")

        self.authenticate(self.user_a)
        self.client.post(f"/api/evaluations/{peer_eval.id}/submit/")

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()

        self.assertEqual(self_eval.status, Evaluation.STATUS_DIFF_REVIEW)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DIFF_REVIEW)

    def test_5_missing_justification_rejected(self):
        """Test 5: Missing or empty justification on POST /score-check/ is rejected"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=2)

        self.authenticate(self.user_a)
        res = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "",  # Empty justification
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_6_valid_justification_saved_and_remaining_count_updated(self):
        """Test 6: Valid justification saved to Answer.justification and remaining_count updated"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=1)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=1)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)  # diff = 3
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=4)  # diff = 3

        # Justify only Q1 out of 2 required questions
        self.authenticate(self.user_a)
        res = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Valid justification for Q1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "diff-review")
        self.assertEqual(res.data["remaining_count"], 1)

        ans1 = Answer.objects.get(evaluation=peer_eval, question=self.question1)
        self.assertEqual(ans1.justification, "Valid justification for Q1")

    def test_7_counterpart_still_pending(self):
        """Test 7: Self submits Score Check first -> Self remains diff-review, remaining_count=0, Peer remains diff-review"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=2)

        # Self submits score check first
        self.authenticate(self.user_b)
        res = self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Self explanation for Q1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "id": self_eval.id,
                "status": "diff-review",
                "remaining_count": 0,
            },
        )

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()

        self.assertEqual(self_eval.status, Evaluation.STATUS_DIFF_REVIEW)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_DIFF_REVIEW)

    def test_8_both_sides_completed(self):
        """Test 8: Self submits first, then Peer submits second -> Both become LOCKED"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)  # diff = 2
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=2)  # diff = 0

        # Self submits score check first
        self.authenticate(self.user_b)
        self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Self explanation",
                    }
                ]
            },
            format="json",
        )

        # Peer submits score check second
        self.authenticate(self.user_a)
        res = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Peer explanation",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "id": peer_eval.id,
                "status": "locked",
                "counterpart_status": "locked",
                "remaining_count": 0,
            },
        )

        peer_eval.refresh_from_db()
        self_eval.refresh_from_db()

        self.assertEqual(peer_eval.status, Evaluation.STATUS_LOCKED)
        self.assertEqual(self_eval.status, Evaluation.STATUS_LOCKED)

    def test_9_cannot_edit_after_locked(self):
        """Test 9: Cannot edit scores or justifications after locked"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )
        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_LOCKED,
        )
        Answer.objects.create(
            evaluation=peer_eval, question=self.question1, score=4, justification="Locked just"
        )

        self.authenticate(self.user_a)
        # Attempt POST /score-check/ on locked evaluation
        sc_res = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Attempted new justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(sc_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt PATCH /answers/ on locked evaluation
        patch_res = self.client.patch(
            f"/api/evaluations/{peer_eval.id}/answers/",
            {"answers": [{"question_id": self.question1.id, "score": 3}]},
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_423_LOCKED)

    def test_10_submission_order_independence(self):
        """Test 10: Score Check behavior is identical regardless of submission order (Peer submits first then Self submits)"""
        self_eval_a = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=self_eval_a, question=self.question1, score=1)
        Answer.objects.create(evaluation=self_eval_a, question=self.question2, score=1)

        peer_assignment_a = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval_a = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment_a,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )
        Answer.objects.create(evaluation=peer_eval_a, question=self.question1, score=3)  # diff = 2
        Answer.objects.create(evaluation=peer_eval_a, question=self.question2, score=1)

        # Peer submits first
        self.authenticate(self.user_a)
        res_p = self.client.post(f"/api/evaluations/{peer_eval_a.id}/submit/")
        self.assertEqual(res_p.status_code, status.HTTP_200_OK)
        peer_eval_a.refresh_from_db()
        self.assertEqual(peer_eval_a.status, Evaluation.STATUS_SUBMITTED)

        # Self submits second
        self.authenticate(self.user_b)
        res_s = self.client.post(f"/api/evaluations/{self_eval_a.id}/submit/")
        self.assertEqual(res_s.status_code, status.HTTP_200_OK)

        peer_eval_a.refresh_from_db()
        self_eval_a.refresh_from_db()

        self.assertEqual(peer_eval_a.status, Evaluation.STATUS_DIFF_REVIEW)
        self.assertEqual(self_eval_a.status, Evaluation.STATUS_DIFF_REVIEW)

    def test_11_invalid_score_check_question_rejected(self):
        """Test 11: Submitting justification for question with difference < 2 is rejected"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=3)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)  # diff = 2 -> required
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=4)  # diff = 1 -> NOT required

        self.authenticate(self.user_a)
        res = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question2.id,  # diff = 1
                        "justification": "Invalid question justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_12_justifications_stored_separately(self):
        """Test 12: Each user's justification is stored on their own Answer without overwriting"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        self_ans = Answer.objects.create(evaluation=self_eval, question=self.question1, score=2)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        peer_ans = Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4)

        # Self submits justification
        self.authenticate(self.user_b)
        self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Self explanation text",
                    }
                ]
            },
            format="json",
        )

        # Peer submits justification
        self.authenticate(self.user_a)
        self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Peer explanation text",
                    }
                ]
            },
            format="json",
        )

        self_ans.refresh_from_db()
        peer_ans.refresh_from_db()

        self.assertEqual(self_ans.justification, "Self explanation text")
        self.assertEqual(peer_ans.justification, "Peer explanation text")
        self.assertNotEqual(self_ans.justification, peer_ans.justification)

    # -------------------------------------------------------------------------
    # SCORE CHECK GET API TESTS
    # -------------------------------------------------------------------------

    def test_get_score_check_response_structure_and_values(self):
        """GET /api/evaluations/{id}/score-check/ returns expected structure and values"""
        self.user_b.designation = "Software Engineer"
        self.user_b.save()

        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(
            evaluation=self_eval, question=self.question1, score=2, justification="Self justification Q1"
        )
        Answer.objects.create(
            evaluation=self_eval, question=self.question2, score=2, justification=None
        )

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(
            evaluation=peer_eval, question=self.question1, score=4, justification="Peer justification Q1"
        )
        Answer.objects.create(
            evaluation=peer_eval, question=self.question2, score=2, justification=None
        )

        # GET request by Self evaluator
        self.authenticate(self.user_b)
        response = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["evaluation_id"], self_eval.id)
        self.assertEqual(data["counterpart_evaluation_id"], peer_eval.id)
        self.assertEqual(
            data["evaluatee"],
            {
                "id": self.user_b.id,
                "first_name": self.user_b.first_name,
                "last_name": self.user_b.last_name,
                "designation": "Software Engineer",
            },
        )
        self.assertEqual(data["remaining_count"], 0)  # Self already justified Q1

        self.assertEqual(len(data["categories"]), 1)
        cat = data["categories"][0]
        self.assertEqual(cat["category_id"], self.category.id)
        self.assertEqual(cat["category_name"], self.category.name)

        self.assertEqual(len(cat["questions"]), 1)
        q1 = cat["questions"][0]
        self.assertEqual(q1["question_id"], self.question1.id)
        self.assertEqual(q1["question_text"], self.question1.text)
        self.assertEqual(q1["your_score"], 2)
        self.assertEqual(q1["counterpart_score"], 4)
        self.assertEqual(q1["difference"], 2)
        self.assertEqual(q1["your_justification"], "Self justification Q1")
        self.assertEqual(q1["counterpart_justification"], "Peer justification Q1")

    def test_get_score_check_self_vs_peer_perspective(self):
        """Self sees Self as 'your', Peer sees Peer as 'your'"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(
            evaluation=self_eval, question=self.question1, score=1, justification="Self text"
        )

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(
            evaluation=peer_eval, question=self.question1, score=4, justification="Peer text"
        )

        # Self GET
        self.authenticate(self.user_b)
        res_self = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(res_self.status_code, status.HTTP_200_OK)
        q_self = res_self.data["categories"][0]["questions"][0]
        self.assertEqual(q_self["your_score"], 1)
        self.assertEqual(q_self["counterpart_score"], 4)
        self.assertEqual(q_self["your_justification"], "Self text")
        self.assertEqual(q_self["counterpart_justification"], "Peer text")

        # Peer GET
        self.authenticate(self.user_a)
        res_peer = self.client.get(f"/api/evaluations/{peer_eval.id}/score-check/")
        self.assertEqual(res_peer.status_code, status.HTTP_200_OK)
        q_peer = res_peer.data["categories"][0]["questions"][0]
        self.assertEqual(q_peer["your_score"], 4)
        self.assertEqual(q_peer["counterpart_score"], 1)
        self.assertEqual(q_peer["your_justification"], "Peer text")
        self.assertEqual(q_peer["counterpart_justification"], "Self text")

    def test_get_score_check_only_diff_gte_2_questions_and_remaining_count(self):
        """Only questions with difference >= 2 are included and remaining_count is calculated correctly"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=1, justification=None)
        Answer.objects.create(evaluation=self_eval, question=self.question2, score=3, justification=None)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4, justification=None)  # diff = 3
        Answer.objects.create(evaluation=peer_eval, question=self.question2, score=4, justification=None)  # diff = 1

        self.authenticate(self.user_b)
        response = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data["remaining_count"], 1)
        self.assertEqual(len(data["categories"]), 1)
        questions = data["categories"][0]["questions"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["question_id"], self.question1.id)
        self.assertEqual(questions[0]["difference"], 3)
        self.assertIsNone(questions[0]["your_justification"])
        self.assertIsNone(questions[0]["counterpart_justification"])

    def test_get_score_check_works_after_post_justification_and_is_read_only(self):
        """GET works after POST justification and does not modify database state"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=1, justification=None)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4, justification=None)

        self.authenticate(self.user_b)

        # Before POST: remaining_count = 1
        res1 = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(res1.data["remaining_count"], 1)
        self.assertIsNone(res1.data["categories"][0]["questions"][0]["your_justification"])

        # POST justification
        post_res = self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "New self justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_200_OK)

        # After POST: remaining_count = 0 and GET returns updated justification
        res2 = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(res2.data["remaining_count"], 0)
        self.assertEqual(
            res2.data["categories"][0]["questions"][0]["your_justification"],
            "New self justification",
        )

    def test_get_score_check_permissions(self):
        """Unauthenticated and unauthorized access is rejected"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )

        # Unauthenticated GET
        self.client.credentials()  # clear credentials
        res_unauth = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Unrelated user GET
        user_c = User.objects.create(email="userc@example.com", first_name="User", last_name="C")
        self.authenticate(user_c)
        res_forbidden = self.client.get(f"/api/evaluations/{self_eval.id}/score-check/")
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Non-existent evaluation
        res_not_found = self.client.get("/api/evaluations/999999/score-check/")
        self.assertEqual(res_not_found.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_modify_completed_score_check_and_counterpart_independence(self):
        """Once current user completes score check, subsequent POST score check is rejected, but counterpart can still submit"""
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_b,
            evaluatee=self.user_b,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=self_eval, question=self.question1, score=1, justification=None)

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle, evaluator=self.user_a, evaluatee=self.user_b
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.user_a,
            evaluatee=self.user_b,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DIFF_REVIEW,
        )
        Answer.objects.create(evaluation=peer_eval, question=self.question1, score=4, justification=None)

        # 1. User B (Self) submits score check
        self.authenticate(self.user_b)
        post_b1 = self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Self initial justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(post_b1.status_code, status.HTTP_200_OK)
        self.assertEqual(post_b1.data["remaining_count"], 0)
        self.assertEqual(post_b1.data["status"], "diff-review")

        # 2. User B attempts second POST score check -> REJECTED
        post_b2 = self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Self attempt to edit justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(post_b2.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. User B attempts to edit original evaluation scores -> REJECTED
        patch_b = self.client.patch(
            f"/api/evaluations/{self_eval.id}/answers/",
            {"answers": [{"question_id": self.question1.id, "score": 3}]},
            format="json",
        )
        self.assertEqual(patch_b.status_code, status.HTTP_423_LOCKED)

        # 4. Peer (User A) can still GET score check (remaining_count = 1 for User A)
        self.authenticate(self.user_a)
        get_a = self.client.get(f"/api/evaluations/{peer_eval.id}/score-check/")
        self.assertEqual(get_a.status_code, status.HTTP_200_OK)
        self.assertEqual(get_a.data["remaining_count"], 1)

        # 5. Peer (User A) submits score check -> BOTH evaluations become LOCKED
        post_a = self.client.post(
            f"/api/evaluations/{peer_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Peer initial justification",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(post_a.status_code, status.HTTP_200_OK)
        self.assertEqual(post_a.data["status"], "locked")
        self.assertEqual(post_a.data["counterpart_status"], "locked")
        self.assertEqual(post_a.data["remaining_count"], 0)

        self_eval.refresh_from_db()
        peer_eval.refresh_from_db()
        self.assertEqual(self_eval.status, Evaluation.STATUS_LOCKED)
        self.assertEqual(peer_eval.status, Evaluation.STATUS_LOCKED)

        # 6. Neither user can modify anything after LOCKED
        self.authenticate(self.user_b)
        post_b3 = self.client.post(
            f"/api/evaluations/{self_eval.id}/score-check/",
            {
                "justifications": [
                    {
                        "question_id": self.question1.id,
                        "justification": "Another attempt",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(post_b3.status_code, status.HTTP_400_BAD_REQUEST)


