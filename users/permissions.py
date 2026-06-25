from rest_framework.permissions import BasePermission

class FirebaseAuthenticated(BasePermission):

    def has_permission(self, request, view):

        return True