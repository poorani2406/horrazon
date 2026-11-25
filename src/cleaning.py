import re
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def clean_phone(value):
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None

def money(value, paise=False):
    text = str(value).replace("₹", "").replace(",", "").strip()
    amount = Decimal(text)
    if paise and amount >= 100000 and amount == amount.to_integral_value():
        amount /= 100
    return amount.quantize(Decimal("0.01"))

def day(value):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError("invalid_date")

def timestamp(value):
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt

def campaign_key(value):
    return " ".join(str(value or "").strip().lower().split())

def status(value):
    value = str(value).strip().upper()
    if value == "CANCELED":
        value = "CANCELLED"
    if value not in {"PLACED","PAID","SHIPPED","DELIVERED","CANCELLED","RETURNED"}:
        raise ValueError("invalid_status")
    return value

def email_valid(value):
    return bool(value and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value).strip()))
