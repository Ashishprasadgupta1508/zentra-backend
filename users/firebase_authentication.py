from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from firebase_admin import auth


class FirebaseAuthentication(BaseAuthentication):

    def authenticate(self, request):

        auth_header = request.headers.get("Authorization")

        if not auth_header:

            return None

        if not auth_header.startswith("Bearer "):

            raise AuthenticationFailed("Invalid token")

        token = auth_header.split(" ")[1]

        try:

            decoded = auth.verify_id_token(token)

            firebase_user = auth.get_user(decoded["uid"])

            return (firebase_user, None)

        except Exception:

            raise AuthenticationFailed("Invalid Firebase Token")