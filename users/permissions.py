from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotAuthenticated

class FirebaseAuthenticated(BasePermission):

    def has_permission(self, request, view):

        if not getattr(request.user, "uid", None):
            raise NotAuthenticated(
                "Authentication required. Send a Firebase ID token or app access token "
                "as 'Authorization: Bearer <token>' with this request."
            )

        return True
