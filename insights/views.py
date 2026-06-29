from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import traceback

from notes.services.gemini import ask_gemini


class ChatView(APIView):

    def post(self, request):

        message = request.data.get("message")

        if not message:
            return Response(
                {
                    "success": False,
                    "message": "Message is required"
                },
                status=400
            )

        try:
            answer = ask_gemini(message)

            return Response({
                "success": True,
                "response": answer
            })

        except Exception as e:
            import traceback
            traceback.print_exc()

            return Response({
                "success": False,
                "error": str(e)
            }, status=500)