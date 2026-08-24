from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    username = None

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=100, blank=True, default="")
    designation = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email