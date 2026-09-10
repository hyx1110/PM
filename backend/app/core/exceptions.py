from typing import Any


class BusinessException(Exception):
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def bad_request(message: str, code: int = 40001, data: Any | None = None) -> BusinessException:
    return BusinessException(400, code, message, data)


def unauthorized(message: str = "not authenticated") -> BusinessException:
    return BusinessException(401, 40101, message)


def forbidden(message: str = "permission denied") -> BusinessException:
    return BusinessException(403, 40301, message)


def not_found(message: str = "resource not found") -> BusinessException:
    return BusinessException(404, 40401, message)


def conflict(message: str, code: int = 40901, data: Any | None = None) -> BusinessException:
    return BusinessException(409, code, message, data)

