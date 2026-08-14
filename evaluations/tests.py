# """
# Integration tests for evaluations API endpoints.
# Run with: python manage.py test evaluations.tests
# """
# from datetime import date

# from django.contrib.auth import get_user_model
# from rest_framework import status
# from rest_framework.test import APITestCase
# from rest_framework_simplejwt.tokens import RefreshToken

# from evaluations.models import Answer, Evaluation, EvaluationCycle, PeerAssignment
# from questions.models import Category, Question

# User = get_user_model()


# class EvaluationsAPITestCase(APITestCase):
#     def setUp(self):
#         self.evaluator = User.objects.create_user(
#             username="evaluator",
#             email="evaluator@example.com",
#             password="pass12345",
#             first_name="Eval",
#             last_name="Uator",
#             role="Engineer",
#         )
#         self.evaluatee = User.objects.create_user(
#             username="evaluatee",
#             email="evaluatee@example.com",
#             password="pass12345",
#             first_name="Thermo",
#             last_name="Flask",
#             role="Frontend Dev",
#         )
#         self.other = User.objects.create_user(
#             username="other",
#             email="other@example.com",
#             password="pass12345",
#             first_name="Other",
#             last_name="Person",
#             role="Backend Dev",
#         )

#         self.cycle = EvaluationCycle.objects.create(
#             name="Q3 2026",
#             status=EvaluationCycle.STATUS_OPEN,
#             start_date=date(2026, 7, 1),
#             end_date=date(2026, 9, 30),
#         )

#         self.category = Category.objects.create(name="Technical Skills", order=1)
#         self.question1 = Question.objects.create(
#             category=self.category,
#             text="Question 1",
#             order=1,
#         )
#         self.question2 = Question.objects.create(
#             category=self.category,
#             text="Question 2",
#             order=2,
#         )

#         self.authenticate(self.evaluator)

#     def authenticate(self, user):
#         token = RefreshToken.for_user(user).access_token
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

#     def test_list_evaluation_cycles_with_status_filter(self):
#         EvaluationCycle.objects.create(
#             name="Q2 2026",
#             status=EvaluationCycle.STATUS_CLOSED,
#             start_date=date(2026, 4, 1),
#             end_date=date(2026, 6, 30),
#         )

#         response = self.client.get("/api/evaluation-cycles/?status=open")
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data), 1)
#         self.assertEqual(response.data[0]["name"], "Q3 2026")
#         self.assertEqual(response.data[0]["status"], "open")

#     def test_available_employees(self):
#         response = self.client.get(
#             f"/api/peer-assignments/available-employees/?cycle_id={self.cycle.id}&search=Thermo"
#         )
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data), 1)
#         self.assertEqual(response.data[0]["first_name"], "Thermo")
#         self.assertEqual(response.data[0]["role"], "Frontend Dev")
#         self.assertEqual(response.data[0]["availability"], "available")

#     def test_create_peer_assignment(self):
#         response = self.client.post(
#             "/api/peer-assignments/",
#             {"cycle_id": self.cycle.id, "evaluatee_id": self.evaluatee.id},
#             format="json",
#         )
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual(response.data["evaluator_id"], self.evaluator.id)
#         self.assertEqual(response.data["evaluatee_id"], self.evaluatee.id)
#         self.assertEqual(response.data["status"], "pending")

#     def test_create_evaluation(self):
#         peer_assignment = PeerAssignment.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#         )

#         response = self.client.post(
#             "/api/evaluations/",
#             {
#                 "cycle_id": self.cycle.id,
#                 "evaluation_type": "peer",
#                 "peer_assignment_id": peer_assignment.id,
#             },
#             format="json",
#         )
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual(response.data["status"], "draft")
#         self.assertEqual(response.data["peer_assignment_id"], peer_assignment.id)

#     def test_get_evaluation_detail(self):
#         peer_assignment = PeerAssignment.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#         )
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             peer_assignment=peer_assignment,
#             evaluation_type=Evaluation.TYPE_PEER,
#             status=Evaluation.STATUS_DRAFT,
#         )

#         response = self.client.get(f"/api/evaluations/{evaluation.id}/")
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertIn("categories", response.data)
#         self.assertEqual(len(response.data["categories"]), 1)

#     def test_save_draft_answers(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_DRAFT,
#         )

#         response = self.client.patch(
#             f"/api/evaluations/{evaluation.id}/answers/",
#             {
#                 "answers": [
#                     {"question_id": self.question1.id, "score": 1, "justification": None},
#                     {
#                         "question_id": self.question2.id,
#                         "score": 5,
#                         "justification": "Found and fixed the root cause.",
#                     },
#                 ]
#             },
#             format="json",
#         )
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(Answer.objects.filter(evaluation=evaluation).count(), 2)

#     def test_get_answer_detail(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_DRAFT,
#         )
#         answer = Answer.objects.create(
#             evaluation=evaluation,
#             question=self.question2,
#             score=5,
#             justification="Found and fixed the root cause.",
#         )

#         response = self.client.get(f"/api/answers/{answer.id}/")
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data["score"], 5)

#     def test_submit_evaluation_success(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_DRAFT,
#         )
#         Answer.objects.create(
#             evaluation=evaluation,
#             question=self.question1,
#             score=1,
#             justification=None,
#         )
#         Answer.objects.create(
#             evaluation=evaluation,
#             question=self.question2,
#             score=5,
#             justification="Found and fixed the root cause.",
#         )

#         response = self.client.post(f"/api/evaluations/{evaluation.id}/submit/")
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data["status"], "locked")
#         self.assertIsNotNone(response.data["submitted_at"])

#     def test_submit_evaluation_missing_justification_for_score_5(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_DRAFT,
#         )
#         Answer.objects.create(
#             evaluation=evaluation,
#             question=self.question1,
#             score=1,
#             justification=None,
#         )
#         Answer.objects.create(
#             evaluation=evaluation,
#             question=self.question2,
#             score=5,
#             justification=None,
#         )

#         response = self.client.post(f"/api/evaluations/{evaluation.id}/submit/")
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertEqual(response.data["detail"], "This evaluation cannot be submitted yet.")
#         self.assertIn(f"question_{self.question2.id}", response.data["errors"])

#     def test_save_answers_locked_evaluation_returns_423(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_LOCKED,
#         )

#         response = self.client.patch(
#             f"/api/evaluations/{evaluation.id}/answers/",
#             {"answers": [{"question_id": self.question1.id, "score": 1, "justification": None}]},
#             format="json",
#         )
#         self.assertEqual(response.status_code, status.HTTP_423_LOCKED)

#     def test_invalid_score_rejected_on_draft_save(self):
#         evaluation = Evaluation.objects.create(
#             cycle=self.cycle,
#             evaluator=self.evaluator,
#             evaluatee=self.evaluatee,
#             evaluation_type=Evaluation.TYPE_SELF,
#             status=Evaluation.STATUS_DRAFT,
#         )

#         response = self.client.patch(
#             f"/api/evaluations/{evaluation.id}/answers/",
#             {"answers": [{"question_id": self.question1.id, "score": 0, "justification": None}]},
#             format="json",
#         )
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
