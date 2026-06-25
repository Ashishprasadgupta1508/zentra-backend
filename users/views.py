from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import auth

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