from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotAuthenticated
import logging

logger = logging.getLogger(__name__)

class FirebaseAuthenticated(BasePermission):

    def has_permission(self, request, view):

        uid = getattr(request.user, "uid", None)
        
        if not uid:
            logger.warning(f"Unauthenticated request to {request.path} from {request.META.get('REMOTE_ADDR', 'unknown')}")
            raise NotAuthenticated(
                "Authentication required. Send a Firebase ID token or JWT access token "
                "as 'Authorization: Bearer <token>' with this request."
            )

        return True
