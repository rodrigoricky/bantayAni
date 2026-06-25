import re
from datetime import datetime, date


RSBSA_PATTERN = re.compile(r"^RSBSA-\d{2}-[A-Z]+-\d{4}-\d+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_rsbsa_format(rsbsa_number: str) -> bool:
    return bool(RSBSA_PATTERN.match(rsbsa_number))


def validate_date_range(date_str: str, min_date: date = None, max_date: date = None) -> bool:
    if not DATE_PATTERN.match(date_str):
        return False
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    if min_date and parsed < min_date:
        return False
    if max_date and parsed > max_date:
        return False
    return True