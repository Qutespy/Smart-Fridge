from datetime import date
from services.ai_cv_service.processor import CVProcessor


def test_ocr_date_extraction_dd_mm_yyyy():
    proc = CVProcessor()
    name, exp_date = proc.process_ocr_result("Молоко Exp: 25.12.2024")
    assert exp_date == date(2024, 12, 25)
    assert name == "Milk"


def test_ocr_date_extraction_yyyy_mm_dd():
    proc = CVProcessor()
    _, exp_date = proc.process_ocr_result("Best before 2024-06-15")
    assert exp_date == date(2024, 6, 15)


def test_ocr_date_extraction_mm_dd_yyyy():
    proc = CVProcessor()
    _, exp_date = proc.process_ocr_result("Exp 03/25/2025")
    assert exp_date == date(2025, 3, 25)


def test_ocr_no_date():
    proc = CVProcessor()
    _, exp_date = proc.process_ocr_result("No date here")
    assert exp_date is None


def test_product_name_extraction():
    proc = CVProcessor()
    name, _ = proc.process_ocr_result("сыр плавленый 01.06.2025")
    assert name == "Cheese"


def test_product_name_fallback():
    proc = CVProcessor()
    name, _ = proc.process_ocr_result("Quinoa organic 01.01.2025")
    assert name == "Quinoa"


def test_validate_detection_high_confidence():
    proc = CVProcessor()
    assert proc.validate_detection(0.85) is True


def test_validate_detection_low_confidence():
    proc = CVProcessor()
    assert proc.validate_detection(0.5) is False


def test_validate_detection_boundary():
    proc = CVProcessor()
    assert proc.validate_detection(0.75) is False
    assert proc.validate_detection(0.76) is True


def test_process_scan_valid():
    proc = CVProcessor()
    result = proc.process_scan("молоко 25.12.2024", 0.9)
    assert result is not None
    assert result.product_name == "Milk"
    assert result.expiration_date == date(2024, 12, 25)
    assert result.confidence == 0.9


def test_process_scan_low_confidence():
    proc = CVProcessor()
    result = proc.process_scan("молоко 25.12.2024", 0.3)
    assert result is None
