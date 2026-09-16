import re
from unicodedata import normalize


EMPLOYEE_NO_PATTERN = re.compile(r"^(?=.*[A-Za-z0-9])[\x21-\x7E]+$")
EMPLOYEE_NO_ERROR = "员工号只能包含英文字母、数字和英文符号，不能包含中文或空格"


def normalize_employee_no(value: str) -> str:
    """Normalize compatibility characters before creation or login lookup."""
    return normalize("NFKC", value).strip()


def is_valid_employee_no(value: str) -> bool:
    return bool(EMPLOYEE_NO_PATTERN.fullmatch(value))
