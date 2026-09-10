from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect


def model_to_dict(instance: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        result[column.key] = value
    return result

