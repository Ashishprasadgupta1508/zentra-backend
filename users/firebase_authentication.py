from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from firebase_admin import auth
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from users.models import User


class AuthenticatedUser:
    def __init__(self, uid, email="", display_name="", photo_url=None, email_verified=False):
        self.uid = uid
        self.email = email
        self.display_name = display_name
        self.photo_url = photo_url
        self.email_verified = email_verified
        self.is_authenticated = True


def from_local_user(user):
    return AuthenticatedUser(
        uid=user.uid,
        email=user.email,
        display_name=user.name,
        photo_url=user.photo_url,
        email_verified=user.email_verified,
    )


def from_firebase_user(firebase_user):
    return AuthenticatedUser(
        uid=firebase_user.uid,
        email=firebase_user.email,
        display_name=firebase_user.display_name or "",
        photo_url=getattr(firebase_user, "photo_url", None),
        email_verified=firebase_user.email_verified,
    )


class FirebaseAuthentication(BaseAuthentication):

    def authenticate(self, request):
        token = self.get_token(request)

        if not token:
            return None

        return self.authenticate_token(token)

    def get_token(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            data = getattr(request, "data", {})
            if hasattr(data, "get"):
                return data.get("token") or data.get("access") or data.get("idToken")
            return None

        parts = auth_header.split()

        if len(parts) == 1:
            return parts[0]

        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Invalid Authorization header")

        return parts[1]

    def authenticate_token(self, token):
        firebase_error = None

        try:
            decoded = auth.verify_id_token(token)
            firebase_user = auth.get_user(decoded["uid"])
            return (from_firebase_user(firebase_user), None)

        except Exception as e:
            firebase_error = e

        try:
            validated_token = UntypedToken(token)
            user_id = validated_token.get("user_id")

            if not user_id:
                raise AuthenticationFailed("JWT token does not contain a user_id")

            user = User.objects.get(id=user_id, is_active=True)
            return (from_local_user(user), validated_token)

        except User.DoesNotExist:
            raise AuthenticationFailed("User not found")

        except (InvalidToken, TokenError, AuthenticationFailed) as jwt_error:
            raise AuthenticationFailed(
                f"Invalid Firebase ID token or access token: {jwt_error or firebase_error}"
            )

    def authenticate_header(self, request):
        return "Bearer"
