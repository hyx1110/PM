from unicodedata import normalize


def normalize_username(value: str) -> str:
    """Return a stable representation without restricting Unicode usernames."""
    return normalize("NFKC", value).strip()
