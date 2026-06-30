from rest_framework import status
from rest_framework.test import APITestCase


class UploadNoteAuthTests(APITestCase):
    def test_upload_requires_bearer_token(self):
        response = self.client.post("/api/notes/upload/", data={})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authorization: Bearer <token>", response.data["detail"])
