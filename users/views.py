from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from firebase_admin import auth

class VerifyUserView(APIView):

    def post(self, request):

        token = request.data.get("token")

        decoded = auth.verify_id_token(token)

        return Response({
            "uid": decoded["uid"],
            "email": decoded.get("email"),
            "name": decoded.get("name")
        })