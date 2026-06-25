from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from firebase_admin import auth

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User



class ProfileView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        firebase_user = request.user

        return Response({

            "uid": firebase_user.uid,

            "email": firebase_user.email,

            "name": firebase_user.display_name,

            "verified": firebase_user.email_verified

        })
class VerifyUserView(APIView):

    def post(self, request):

        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            decoded = auth.verify_id_token(token)

            firebase_user = auth.get_user(decoded["uid"])

            if not firebase_user.email_verified:

                return Response(
                    {
                        "success": False,
                        "message": "Please verify your email first."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return Response({

                "success": True,

                "uid": firebase_user.uid,

                "email": firebase_user.email,

                "name": firebase_user.display_name,

                "email_verified": firebase_user.email_verified

            })

        except Exception as e:

            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
class LoginView(APIView):

    def post(self, request):

        token = request.data.get("token")

        if not token:
            return Response(
                {
                    "success": False,
                    "message": "Token is required"
                },
                status=400
            )

        try:

            decoded = auth.verify_id_token(token)

            firebase_user = auth.get_user(decoded["uid"])

            if not firebase_user.email_verified:

                return Response(
                    {
                        "success": False,
                        "message": "Please verify your email first."
                    },
                    status=403
                )

            user = User.objects.get(uid=firebase_user.uid)

            refresh = RefreshToken.for_user(user)

            return Response({

                "success": True,

                "access": str(refresh.access_token),

                "refresh": str(refresh),

                "user": {

                    "uid": user.uid,
                    "email": user.email,
                    "name": user.name

                }

            })

        except Exception as e:

            return Response(
                {
                    "success": False,
                    "error": str(e)
                },
                status=401
            )
        
class SignupView(APIView):

    def post(self, request):

        token = request.data.get("token")

        decoded = auth.verify_id_token(token)

        uid = decoded["uid"]

        email = decoded.get("email")

        name = decoded.get("name", "")

        user, created = User.objects.get_or_create(
            uid=uid,
            defaults={
                "email": email,
                "name": name
            }
        )

        return Response({
            "success": True,
            "new_user": created
        })