from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from notes.services.gemini import ask_gemini


class ChatView(APIView):

    def post(self, request):

        print("request.data =", request.data)
        print("request.body =", request.body)

        message = request.data.get("message")

        if not message:
            return Response({
                "success": False,
                "request_data": request.data,
                "body": request.body.decode("utf-8"),
                "message": "Message is required"
            }, status=400)

        answer = ask_gemini(message)

        return Response({
            "success": True,
            "response": answer
        })