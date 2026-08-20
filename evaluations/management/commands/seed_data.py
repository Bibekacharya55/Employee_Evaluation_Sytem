from django.core.management.base import BaseCommand
from accounts.models import User
from questions.models import Category, Question
from evaluations.models import EvaluationCycle

class Command(BaseCommand):
    help = "Create seed data for Employee Evaluation System"

    def handle(self, *args, **options):

        users = [
            {
                "email": "manager@example.com",
                "username": "manager",
                "role": "manager",
                "designation": "Manager",
            },
            {
                "email": "employee1@example.com",
                "username": "employee1",
                "role": "employee",
                "designation": "Software Developer",
            },
            {
                "email": "employee2@example.com",
                "username": "employee2",
                "role": "employee",
                "designation": "Software Developer",
            },
            {
                "email": "employee3@example.com",
                "username": "employee3",
                "role": "employee",
                "designation": "QA Engineer",
            },
            {
                "email": "employee4@example.com",
                "username": "employee4",
                "role": "employee",
                "designation": "Backend Developer",
            },
        ]

        for data in users:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "username": data["username"],
                    "role": data["role"],
                    "designation": data["designation"],
                },
            )

            if created:
                user.set_password("password123")
                user.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created user: {user.email}"
                    )
                )
            else:
                self.stdout.write(
                    f"User already exists: {user.email}"
                )

        self.stdout.write(
            self.style.SUCCESS("User seed data completed!")
        )
        categories = [
            {
                "name": "Technical Skills",
                "order": 1,
                "questions": [
                    "How effectively does the employee apply technical knowledge?",
                    "How well does the employee solve technical problems?",
                    "How effectively does the employee learn new technologies?",
                ],
            },
            {
                "name": "Communication",
                "order": 2,
                "questions": [
                    "How clearly does the employee communicate with others?",
                    "How effectively does the employee share information?",
                    "How well does the employee listen to feedback?",
                ],
            },
            {
                "name": "Teamwork",
                "order": 3,
                "questions": [
                    "How effectively does the employee work with team members?",
                    "How well does the employee support team members?",
                    "How positively does the employee contribute to the team?",
                ],
            },
            {
                "name": "Problem Solving",
                "order": 4,
                "questions": [
                    "How effectively does the employee identify problems?",
                    "How effectively does the employee develop solutions?",
                    "How well does the employee handle challenging situations?",
                ],
            },
        ]

        for category_data in categories:

            category, category_created = Category.objects.get_or_create(
                name=category_data["name"],
                defaults={
                    "order": category_data["order"],
                },
            )

            if category_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created category: {category.name}"
                    )
                )
            else:
                self.stdout.write(
                    f"Category already exists: {category.name}"
                )

            for question_order, question_text in enumerate(
                category_data["questions"],
                start=1,
            ):
                question, question_created = Question.objects.get_or_create(
                    category=category,
                    text=question_text,
                    defaults={
                        "order": question_order,
                    },
                )

                if question_created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created question: {question.text}"
                        )
                    )
                else:
                    self.stdout.write(
                        f"  Question already exists: {question.text}"
                    )

        cycle, cycle_created = EvaluationCycle.objects.get_or_create(
            name="2026 Performance Evaluation",
            defaults={
                "status": EvaluationCycle.STATUS_OPEN,
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
            },
        )

        if cycle_created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created evaluation cycle: {cycle.name}"
                )
            )
        else:
            self.stdout.write(
                f"Evaluation cycle already exists: {cycle.name}"
            )
