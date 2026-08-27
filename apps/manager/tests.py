from datetime import date
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.evaluations.models import Answer, Evaluation, EvaluationCycle, PeerAssignment
from apps.questions.models import Category, Question

User = get_user_model()


class ManagerAPITestCase(APITestCase):
    def setUp(self):
        # Staff manager
        self.staff_manager = User.objects.create(
            email="manager@company.com",
            first_name="Manager",
            last_name="User",
            is_staff=True,
        )
        self.staff_manager.set_password("pass12345")
        self.staff_manager.save()

        # Non-staff employee 1
        self.employee = User.objects.create(
            email="maya@company.com",
            first_name="Maya",
            last_name="Shrestha",
            designation="Backend Dev",
            is_staff=False,
        )
        self.employee.set_password("pass12345")
        self.employee.save()

        # Non-staff employee 2 (Peer evaluator)
        self.peer_evaluator = User.objects.create(
            email="anuj@company.com",
            first_name="Anuj",
            last_name="Shrestha",
            is_staff=False,
        )
        self.peer_evaluator.set_password("pass12345")
        self.peer_evaluator.save()

        self.cycle = EvaluationCycle.objects.create(
            name="Q3 2026",
            status=EvaluationCycle.STATUS_OPEN,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
        )

        self.category = Category.objects.create(name="Communication", order=1)
        self.question = Question.objects.create(
            category=self.category,
            text="Gives and receives feedback in meetings.",
            order=1,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # -------------------------------------------------------------------------
    # MANAGER DASHBOARD TESTS (1-6)
    # -------------------------------------------------------------------------

    def test_1_authenticated_staff_user_can_access_dashboard(self):
        self.authenticate(self.staff_manager)
        res = self.client.get("/api/manager/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_2_non_staff_user_receives_403_on_dashboard(self):
        self.authenticate(self.employee)
        res = self.client.get("/api/manager/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_3_to_6_dashboard_data_and_ready_for_final_review(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_DRAFT,
        )

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_DRAFT,
        )

        self.authenticate(self.staff_manager)

        res1 = self.client.get("/api/manager/dashboard/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        emp_data = next((item for item in res1.data if item["employee"]["id"] == self.employee.id), None)
        self.assertIsNotNone(emp_data)
        self.assertEqual(emp_data["employee"]["first_name"], "Maya")
        self.assertEqual(emp_data["employee"]["last_name"], "Shrestha")
        self.assertEqual(emp_data["self_evaluation_status"], "draft")
        self.assertEqual(emp_data["peer_evaluation_statuses"], ["draft"])
        self.assertFalse(emp_data["ready_for_final_review"])

        self_eval.status = Evaluation.STATUS_LOCKED
        self_eval.save()
        peer_eval.status = Evaluation.STATUS_LOCKED
        peer_eval.save()

        res2 = self.client.get("/api/manager/dashboard/")
        emp_data2 = next((item for item in res2.data if item["employee"]["id"] == self.employee.id), None)
        self.assertEqual(emp_data2["self_evaluation_status"], "locked")
        self.assertEqual(emp_data2["peer_evaluation_statuses"], ["locked"])
        self.assertTrue(emp_data2["ready_for_final_review"])

    # -------------------------------------------------------------------------
    # MANAGER REVIEW TESTS (7-13)
    # -------------------------------------------------------------------------

    def test_7_staff_manager_can_retrieve_employee_review(self):
        self.authenticate(self.staff_manager)
        res = self.client.get(f"/api/manager/employees/{self.employee.id}/review/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_8_non_staff_receives_403_on_employee_review(self):
        self.authenticate(self.employee)
        res = self.client.get(f"/api/manager/employees/{self.employee.id}/review/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_9_to_13_employee_review_structure_and_nested_evaluations(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )
        Answer.objects.create(
            evaluation=self_eval,
            question=self.question,
            score=4,
            justification="Self justification",
        )

        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_LOCKED,
        )
        Answer.objects.create(
            evaluation=peer_eval,
            question=self.question,
            score=2,
            justification="Peer justification",
        )

        self.authenticate(self.staff_manager)
        res = self.client.get(f"/api/manager/employees/{self.employee.id}/review/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        emp_info = res.data["employee"]
        self.assertEqual(emp_info["id"], self.employee.id)
        self.assertEqual(emp_info["first_name"], "Maya")
        self.assertEqual(emp_info["last_name"], "Shrestha")
        self.assertEqual(emp_info["email"], "maya@company.com")
        self.assertTrue(res.data["ready_for_final_review"])

        self_data = res.data["self_evaluation"]
        self.assertEqual(self_data["id"], self_eval.id)
        self.assertEqual(self_data["status"], "locked")
        self.assertEqual(len(self_data["categories"]), 1)

        peer_data_list = res.data["peer_evaluations"]
        self.assertEqual(len(peer_data_list), 1)
        peer_item = peer_data_list[0]
        self.assertEqual(peer_item["id"], peer_eval.id)
        self.assertEqual(peer_item["evaluator"]["id"], self.peer_evaluator.id)
        self.assertEqual(peer_item["evaluator"]["first_name"], "Anuj")
        self.assertEqual(peer_item["evaluator"]["last_name"], "Shrestha")

        cat_item = peer_item["categories"][0]
        self.assertEqual(cat_item["name"], "Communication")
        q_item = cat_item["questions"][0]
        self.assertEqual(q_item["id"], self.question.id)
        self.assertEqual(q_item["answer"]["score"], 2)
        self.assertEqual(q_item["answer"]["justification"], "Peer justification")

    # -------------------------------------------------------------------------
    # FINAL REVIEW TESTS (14-20)
    # -------------------------------------------------------------------------

    def test_14_to_16_create_final_review_success_and_permission(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )
        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
        )
        peer_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_LOCKED,
        )

        self.authenticate(self.employee)
        res_non_staff = self.client.post(
            f"/api/manager/employees/{self.employee.id}/final-review/",
            {"self_eval_id": self_eval.id, "comments": "Good quarter"},
            format="json",
        )
        self.assertEqual(res_non_staff.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.staff_manager)
        res_staff = self.client.post(
            f"/api/manager/employees/{self.employee.id}/final-review/",
            {"self_eval_id": self_eval.id, "comments": "Strong quarter performance."},
            format="json",
        )
        self.assertEqual(res_staff.status_code, status.HTTP_201_CREATED)

        self.assertEqual(res_staff.data["manager_id"], self.staff_manager.id)
        self.assertEqual(res_staff.data["employee_id"], self.employee.id)
        self.assertEqual(res_staff.data["self_eval_id"], self_eval.id)
        self.assertEqual(res_staff.data["comments"], "Strong quarter performance.")
        self.assertEqual(res_staff.data["status"], "completed")

    def test_17_final_review_rejected_when_self_not_locked(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_SUBMITTED,
        )
        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
        )
        Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_LOCKED,
        )

        self.authenticate(self.staff_manager)
        res = self.client.post(
            f"/api/manager/employees/{self.employee.id}/final-review/",
            {"self_eval_id": self_eval.id, "comments": "Comments"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            res.data["detail"],
            "Self and peer evaluations must all be locked before performing the final review.",
        )

    def test_18_final_review_rejected_when_peer_not_locked(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )
        peer_assignment = PeerAssignment.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
        )
        Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.peer_evaluator,
            evaluatee=self.employee,
            peer_assignment=peer_assignment,
            evaluation_type=Evaluation.TYPE_PEER,
            status=Evaluation.STATUS_SUBMITTED,
        )

        self.authenticate(self.staff_manager)
        res = self.client.post(
            f"/api/manager/employees/{self.employee.id}/final-review/",
            {"self_eval_id": self_eval.id, "comments": "Comments"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_19_self_eval_id_cannot_be_used_for_another_employee(self):
        self_eval = Evaluation.objects.create(
            cycle=self.cycle,
            evaluator=self.employee,
            evaluatee=self.employee,
            evaluation_type=Evaluation.TYPE_SELF,
            status=Evaluation.STATUS_LOCKED,
        )

        self.authenticate(self.staff_manager)
        res = self.client.post(
            f"/api/manager/employees/{self.peer_evaluator.id}/final-review/",
            {"self_eval_id": self_eval.id, "comments": "Comments"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
