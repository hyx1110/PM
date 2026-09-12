import re
from unicodedata import normalize


USERNAME_PATTERN = re.compile(r"^(?=.*[A-Za-z0-9])[\x21-\x7E]+$")
USERNAME_ERROR = "用户名只能包含英文字母、数字和英文符号，不能包含中文或空格"


def normalize_username(value: str) -> str:
    """Normalize compatibility characters before creation or login lookup."""
    return normalize("NFKC", value).strip()


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(value))
