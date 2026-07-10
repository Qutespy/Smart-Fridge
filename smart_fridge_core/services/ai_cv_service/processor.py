import re
from datetime import date, datetime
from typing import Optional, Tuple
import logging
from core.schemas import ScanResult

logger = logging.getLogger(__name__)


class CVProcessor:
    """Обработка результатов OCR для распознавания продуктов"""

    # Расширенный словарь продуктов для сопоставления
    PRODUCT_KEYWORDS = {
        'молоко': 'Milk',
        'milk': 'Milk',
        'кефир': 'Kefir',
        'сыр': 'Cheese',
        'cheese': 'Cheese',
        'йогурт': 'Yogurt',
        'хлеб': 'Bread',
        'bread': 'Bread',
        'яйца': 'Eggs',
        'eggs': 'Eggs',
        'масло': 'Butter',
        'мясо': 'Meat',
        'meat': 'Meat',
        'курица': 'Chicken',
        'chicken': 'Chicken',
        'овощи': 'Vegetables',
        'фрукты': 'Fruits'
    }

    def process_ocr_result(self, text: str) -> Tuple[str, Optional[date]]:
        """
        Извлекает название продукта и дату из строки OCR.
        Возвращает (product_name, expiration_date)
        """
        text_lower = text.lower()

        # Поиск названия продукта
        product_name = self._extract_product_name(text_lower)

        # Поиск даты
        expiration_date = self._extract_date(text)

        return product_name, expiration_date

    def _extract_product_name(self, text: str) -> str:
        """Извлечение названия продукта из текста"""
        for keyword, product in self.PRODUCT_KEYWORDS.items():
            if keyword in text:
                return product

        # Если не нашли, берем первое слово
        words = text.split()
        if words:
            return words[0].capitalize()

        return "Unknown Product"

    def _extract_date(self, text: str) -> Optional[date]:
        """Извлечение даты из текста (поддерживает несколько форматов)"""
        # Формат ДД.ММ.ГГГГ
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if match:
            d, m, y = match.groups()
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                pass

        # Формат ГГГГ-ММ-ДД
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
        if match:
            y, m, d = match.groups()
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                pass

        # Формат ММ/ДД/ГГГГ
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
        if match:
            m, d, y = match.groups()
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                pass

        return None

    def validate_detection(self, confidence: float) -> bool:
        """Отсеивание ложных срабатываний нейронки"""
        return confidence > 0.75

    def process_scan(self, ocr_text: str, confidence: float) -> Optional[ScanResult]:
        """Полный цикл обработки сканирования"""
        if not self.validate_detection(confidence):
            logger.warning(f"Low confidence detection: {confidence}")
            return None

        product_name, exp_date = self.process_ocr_result(ocr_text)

        return ScanResult(
            product_name=product_name,
            confidence=confidence,
            expiration_date=exp_date,
            barcode=None  # Может быть извлечен отдельно
        )