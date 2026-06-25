from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from firebase_admin import auth

from .models import User


class VerifyUserView(APIView):

    def post(self, request):

        token = request.data.get("token")

        decoded = auth.verify_id_token(token)

        return Response({
            "uid": decoded["uid"],
            "email": decoded.get("email"),
            "name": decoded.get("name")
        })


class SignupView(APIView):

    def post(self, request):

        token = request.data.get("token")

        if not token:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            decoded = auth.verify_id_token(token)

            uid = decoded["uid"]
            email = decoded.get("email")
            name = decoded.get("name", "")
            photo = decoded.get("picture", "")
            verified = decoded.get("email_verified", False)

            user, created = User.objects.get_or_create(
                uid=uid,
                defaults={
                    "email": email,
                    "name": name,
                    "photo_url": photo,
                    "email_verified": verified,
                }
            )

            if not created:
                user.email = email
                user.name = name
                user.photo_url = photo
                user.email_verified = verified
                user.save()

            return Response({
                "success": True,
                "new_user": created
            })

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )