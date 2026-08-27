from datetime import date
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.evaluations.models import Answer, Evaluation, EvaluationCycle, PeerAssignment
from apps.questions.models import Category, Question

User = get_user_model()


class ReportsAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            email="report_user@company.com",
            first_name="Report",
            last_name="User",
            is_staff=True,
        )
        self.user.set_password("pass12345")
        self.user.save()

        self.employee = User.objects.create(
            email="maya@company.com",
            first_name="Maya",
            last_name="Shrestha",
            designation="Backend Dev",
        )

        self.peer = User.objects.create(
            email="anuj@company.com",
            first_name="Anuj",
            last_name="Shrestha",
        )

        self.cycle1 = EvaluationCycle.objects.create(
            name="Q3 2026",
            status=EvaluationCycle.STATUS_OPEN,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
        )

        self.cycle2 = EvaluationCycle.objects.create(
            name="Q2 2026",
            status=EvaluationCycle.STATUS_CLOSED,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 6, 30),
        )

        self.category = Category.objects.create(name="Communication", order=1)
        self.question = Question.objects.create(
            category=self.category,
            text="Gives and receives feedback in meetings.",
            order=1,
        )

        self.self_eval = Evaluation.objects.create(
            cycle=self.cycle1,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )
        Answer.objects.create(
            evaluation=self.self_eval,
            question=self.question,
            score=4,
            justification="I actively ask for feedback in every retro.",
        )

        self.peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle1,
            evaluator=self.peer,
            evaluatee=self.employee,
        )
        self.peer_eval = Evaluation.objects.create(
            cycle=self.cycle1,
            evaluator=self.peer,
            evaluatee=self.employee,
            peer_assignment=self.peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_SUBMITTED,
        )
        Answer.objects.create(
            evaluation=self.peer_eval,
            question=self.question,
            score=2,
            justification="I only saw two written updates from them all quarter.",
        )

        self.authenticate(self.user)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # -------------------------------------------------------------------------
    # REPORT LIST & DETAIL TESTS (21-26)
    # -------------------------------------------------------------------------

    def test_21_to_22_report_list_returns_real_evaluations_and_filters_by_cycle(self):
        res1 = self.client.get(f"/api/reports/?cycle_id={self.cycle1.id}")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res1.data), 2)

        peer_row = next(r for r in res1.data if r["evaluation_id"] == self.peer_eval.id)
        self.assertEqual(peer_row["employee"], "Maya Shrestha")
        self.assertEqual(peer_row["evaluating"], "Anuj Shrestha")
        self.assertEqual(peer_row["status"], "submitted")
        self.assertEqual(peer_row["overall_score"], 2.0)

        res2 = self.client.get(f"/api/reports/?cycle_id={self.cycle2.id}")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res2.data), 0)

    def test_23_to_26_report_detail_returns_categories_scores_diffs_justifications(self):
        res = self.client.get(f"/api/reports/{self.peer_eval.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(res.data["evaluatee"]["id"], self.employee.id)
        self.assertEqual(res.data["evaluatee"]["first_name"], "Maya")
        self.assertEqual(res.data["evaluatee"]["last_name"], "Shrestha")
        self.assertEqual(res.data["evaluatee"]["role"], "Backend Dev")

        self.assertEqual(res.data["evaluator"]["id"], self.peer.id)
        self.assertEqual(res.data["evaluator"]["first_name"], "Anuj")
        self.assertEqual(res.data["evaluator"]["last_name"], "Shrestha")

        self.assertEqual(res.data["status"], "submitted")
        self.assertEqual(res.data["overall_score"], 2.0)

        categories = res.data["categories"]
        self.assertEqual(len(categories), 1)
        cat = categories[0]
        self.assertEqual(cat["name"], "Communication")

        questions = cat["questions"]
        self.assertEqual(len(questions), 1)
        q = questions[0]

        self.assertEqual(q["question_text"], "Gives and receives feedback in meetings.")
        self.assertEqual(q["peer_score"], 2)
        self.assertEqual(q["self_score"], 4)
        self.assertEqual(q["diff"], 2)
        self.assertEqual(q["self_justification"], "I actively ask for feedback in every retro.")
        self.assertEqual(q["peer_justification"], "I only saw two written updates from them all quarter.")

    # -------------------------------------------------------------------------
    # CSV EXPORT TESTS (27-34)
    # -------------------------------------------------------------------------

    def test_27_to_33_csv_export_headers_answers_and_filtering(self):
        res = self.client.get(f"/api/reports/export/?cycle_id={self.cycle1.id}&format=csv")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", res["Content-Disposition"])

        content = res.content.decode("utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        header = lines[0]
        self.assertEqual(
            header,
            "employee,evaluator,evaluation_type,category,question,score,justification,status,submitted_at,created_at,updated_at",
        )

        self.assertEqual(len(lines), 3)
        self.assertIn("Maya Shrestha", content)
        self.assertIn("Anuj Shrestha", content)
        self.assertIn("Communication", content)
        self.assertIn("Gives and receives feedback in meetings.", content)
        self.assertIn("I actively ask for feedback in every retro.", content)

        res_empty = self.client.get(f"/api/reports/export/?cycle_id={self.cycle2.id}&format=csv")
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        lines_empty = [line.strip() for line in res_empty.content.decode("utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines_empty), 1)

    def test_34_unsupported_export_format_handled(self):
        res = self.client.get(f"/api/reports/export/?cycle_id={self.cycle1.id}&format=pdf")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
