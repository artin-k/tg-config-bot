from __future__ import annotations


WITHDRAWAL_STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "approved": "تایید شده",
    "rejected": "رد شده",
    "paid": "پرداخت شد",
    "cancelled": "لغو شده",
}

WITHDRAWAL_DESTINATION_LABELS = {
    "card": "کارت",
    "sheba": "شبا",
}

_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def format_withdrawal_status_fa(status: str | None) -> str:
    return WITHDRAWAL_STATUS_LABELS.get(status or "", status or "-")


def format_withdrawal_destination_fa(destination_type: str | None) -> str:
    return WITHDRAWAL_DESTINATION_LABELS.get(destination_type or "", destination_type or "-")


def normalize_card_number(value: str | None) -> str | None:
    normalized = _normalize_digits(value).replace(" ", "").replace("-", "")
    if len(normalized) != 16 or not normalized.isdigit():
        return None
    return normalized


def normalize_sheba_number(value: str | None) -> str | None:
    normalized = _normalize_digits(value).replace(" ", "").replace("-", "").upper()
    if len(normalized) != 26 or not normalized.startswith("IR") or not normalized[2:].isdigit():
        return None
    return normalized


def mask_card_number(value: str | None) -> str:
    normalized = normalize_card_number(value) or _normalize_digits(value).replace(" ", "").replace("-", "")
    if len(normalized) < 8:
        return normalized or "-"
    return f"{normalized[:4]}********{normalized[-4:]}"


def mask_sheba(value: str | None) -> str:
    normalized = normalize_sheba_number(value) or _normalize_digits(value).replace(" ", "").replace("-", "").upper()
    if len(normalized) < 8:
        return normalized or "-"
    return f"{normalized[:4]}***************{normalized[-4:]}"


def mask_destination(destination_type: str | None, destination_number: str | None) -> str:
    if destination_type == "card":
        return mask_card_number(destination_number)
    if destination_type == "sheba":
        return mask_sheba(destination_number)
    return destination_number or "-"


def _normalize_digits(value: str | None) -> str:
    return str(value or "").strip().translate(_DIGIT_TRANSLATION)
