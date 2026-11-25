from decimal import Decimal
from src.cleaning import clean_phone, money, day, status, email_valid

def test_phone_indian_formats():
    assert clean_phone("+91 98765 43210") == "9876543210"
    assert clean_phone("09876543210") == "9876543210"

def test_money_decimal():
    assert money("₹1,250.50") == Decimal("1250.50")

def test_paise():
    assert money("129900", paise=True) == Decimal("1299.00")

def test_date_formats():
    assert str(day("01/08/2026")) == "2026-08-01"

def test_status_spelling():
    assert status("CANCELED") == "CANCELLED"

def test_email_validation():
    assert email_valid("a@example.com")
    assert not email_valid("bad-email")

def test_campaign_key_normalization():
    from src.cleaning import campaign_key
    assert campaign_key(" Summer   Sale ") == campaign_key("summer sale")
