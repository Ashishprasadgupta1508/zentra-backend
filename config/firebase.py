import os
import firebase_admin
from firebase_admin import credentials
import logging

logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_path = os.path.join(BASE_DIR, "firebase-service-account.json")
    
    if os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            logger.warning("Firebase features will be unavailable")
    else:
        logger.warning(f"Firebase credentials file not found at {cred_path}. Firebase features will be unavailable.")