from app.logging_config import scrub_event
from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_vietnamese_national_id() -> None:
    out = scrub_text("CCCD: 079123456789")
    assert "079123456789" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    card_number = "4111 1111 1111 1111"
    out = scrub_text(f"Card: {card_number}")
    assert card_number not in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_event_redacts_nested_log_fields() -> None:
    event = {
        "event": "request_received",
        "session_id": "student@example.com",
        "payload": {"details": ["CCCD 079123456789"]},
    }
    out = scrub_event(None, "info", event)
    assert "student@example.com" not in str(out)
    assert "079123456789" not in str(out)
