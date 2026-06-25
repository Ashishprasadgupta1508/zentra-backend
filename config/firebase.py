import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage

cred = credentials.Certificate(
    "firebase-service-account.json"
)

firebase_admin.initialize_app(
    cred,
    {
        "storageBucket": "zentra-8a600.firebasestorage.app"
    }
)