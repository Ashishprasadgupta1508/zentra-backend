from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import traceback

from notes.services.gemini import ask_gemini


class ChatView(APIView):

    def post(self, request):

        try:
            print("request.data =", request.data)

            message = request.data.get("message")

            # QueryDict fallback
            if not message:
                import json

                body = request.data.get("_content")

                if body:
                    body = json.loads(body)
                    message = body.get("message")

            print("message =", message)

            if not message:
                return Response(
                    {
                        "success": False,
                        "message": "Message is required"
                    },
                    status=400
                )

            print("Calling Gemini...")

            answer = ask_gemini(message)

            print("Gemini Response:", answer)

            return Response({
                "success": True,
                "response": answer
            })

        except Exception as e:

            traceback.print_exc()

            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "type": str(type(e))
                },
                status=500
            )