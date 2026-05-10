import secrets


def generate_tracking_code() -> str:
    return secrets.token_hex(5)


def generate_referral_code(telegram_id: int) -> str:
    return f"ref{telegram_id:x}"
