import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class BeijingFormatter(logging.Formatter):
    converter = staticmethod(
        lambda timestamp: datetime.fromtimestamp(timestamp, BEIJING_TZ).timetuple()
    )


class HourlyFolderFileHandler(logging.Handler):
    """Write logs to logs/YYYY-MM-DD/app-HH.log in Beijing time."""

    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir.resolve()
        self._period: str | None = None
        self._stream = None

    def _ensure_stream(self) -> None:
        now = datetime.now(BEIJING_TZ)
        period = now.strftime("%Y-%m-%d/%H")
        if self._stream is not None and self._period == period:
            return
        if self._stream is not None:
            self._stream.close()
        day_dir = self.base_dir / now.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        self._stream = (day_dir / f"app-{now:%H}.log").open(
            "a", encoding="utf-8"
        )
        self._period = period

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ensure_stream()
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        super().close()


def configure_logging(extra_logger_names: tuple[str, ...] = ()) -> None:
    formatter = BeijingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    file_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, HourlyFolderFileHandler)
        ),
        None,
    )
    if file_handler is None:
        file_handler = HourlyFolderFileHandler(Path("logs"))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logger_names = (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        *extra_logger_names,
    )
    for logger_name in dict.fromkeys(logger_names):
        app_logger = logging.getLogger(logger_name)
        for handler in app_logger.handlers:
            handler.setFormatter(formatter)
        if not app_logger.propagate and file_handler not in app_logger.handlers:
            app_logger.addHandler(file_handler)
