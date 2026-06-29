from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from firebase_admin import auth


class FirebaseAuthentication(BaseAuthentication):

    def authenticate(self, request):

        auth_header = request.headers.get("Authorization")

        print("HEADER:", auth_header)

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Invalid Authorization header")

        token = parts[1]

        try:
            decoded = auth.verify_id_token(token)

            print("DECODED:", decoded)

            firebase_user = auth.get_user(decoded["uid"])

            print("FIREBASE UID:", firebase_user.uid)

            return (firebase_user, None)

        except Exception as e:

            print("AUTH ERROR:", e)

            raise AuthenticationFailed(str(e))
