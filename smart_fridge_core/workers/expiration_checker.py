from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from sqlalchemy.orm import Session
from services.inventory_service.manager import InventoryManager
from services.notification_service.pusher import NotificationService
from core.database import SessionLocal
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def check_expired_products():
    """Проверка просроченных продуктов (запускается каждый день в 9:00)"""
    logger.info("Running expiration check...")

    db: Session = SessionLocal()
    try:
        inventory_manager = InventoryManager(db)
        notification_service = NotificationService()

        # Получаем все уникальные family_id
        # В реальности нужно получать из БД

        # Пример для одной семьи
        # alerts = inventory_manager.get_alerts(family_id, date.today())
        # Отправляем уведомления

        logger.info("Expiration check completed")
    except Exception as e:
        logger.error(f"Error in expiration check: {e}")
    finally:
        db.close()


def start_scheduler():
    """Запуск планировщика задач"""
    scheduler.add_job(
        check_expired_products,
        'cron',
        hour=9,
        minute=0,
        id='expiration_check'
    )
    scheduler.start()
    logger.info("Scheduler started")