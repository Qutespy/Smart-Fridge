import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        if settings.FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            self.initialized = True
        else:
            self.initialized = False
            logger.warning("Firebase not configured")

    def send_push_notification(self, device_token: str, title: str, body: str, data: Dict = None):
        """Отправка push-уведомления на устройство"""
        if not self.initialized:
            logger.warning("Push notification not sent - Firebase not configured")
            return

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=device_token,
        )

        try:
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return response
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise

    def send_expiration_alerts(self, user_tokens: List[str], expired_items: List[str],
                               expiring_items: List[str]):
        """Отправка уведомлений о просрочке"""
        if expired_items:
            self.send_push_notification(
                device_token=user_tokens[0],  # В реальности для каждого токена
                title="⚠️ Продукты просрочены!",
                body=f"Продукты просрочены: {', '.join(expired_items[:3])}",
                data={"type": "expired", "items": expired_items}
            )

        if expiring_items:
            self.send_push_notification(
                device_token=user_tokens[0],
                title="⏰ Продукты скоро испортятся",
                body=f"Скоро испортятся: {', '.join(expiring_items[:3])}",
                data={"type": "expiring", "items": expiring_items}
            )