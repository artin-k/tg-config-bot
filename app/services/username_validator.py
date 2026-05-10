import re


USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


def validate_username(username: str) -> tuple[bool, str]:
    normalized = username.strip()

    if normalized != username or " " in normalized:
        return False, "نام کاربری نباید فاصله داشته باشد."
    if not (3 <= len(normalized) <= 20):
        return False, "نام کاربری باید بین ۳ تا ۲۰ کاراکتر باشد."
    if not normalized[0].isalpha() or not normalized[0].isascii():
        return False, "نام کاربری باید با حرف انگلیسی شروع شود."
    if normalized.endswith("_"):
        return False, "نام کاربری نباید با آندرلاین تمام شود."
    if not USERNAME_RE.fullmatch(normalized):
        return False, "فقط حروف انگلیسی، عدد و آندرلاین مجاز است."

    return True, normalized
