from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsManager(BasePermission):

    message = "Only managers can access this endpoint."

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated
            and (
                request.user.role == User.ROLE_MANAGER
                or request.user.is_superuser
            )
        )