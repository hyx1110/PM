import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo


class BeijingFormatter(logging.Formatter):
    converter = staticmethod(lambda timestamp: datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai")).timetuple())


def configure_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = BeijingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    log_path = (log_dir / "app.log").resolve()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Uvicorn configures logging before the application lifespan starts, so a
    # later basicConfig() call is ignored. Reuse its console handler, apply the
    # Beijing formatter, and add the rotating application file only once.
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).resolve() == log_path
        for handler in root_logger.handlers
    ):
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(logger_name).handlers:
            handler.setFormatter(formatter)
