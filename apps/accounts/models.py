from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    username = None

    ROLE_EMPLOYEE = "employee"
    ROLE_MANAGER = "manager"

    ROLE_CHOICES = [
        (ROLE_EMPLOYEE, "Employee"),
        (ROLE_MANAGER, "Manager"),
    ]

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_EMPLOYEE,
    )

    designation = models.CharField(
        max_length=100,
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email