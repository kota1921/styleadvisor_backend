import os
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

class TimedFileLoggerConfigurator:
    def __init__(self, log_path: str = "logs/app.log", backup_days: int = 7, level: int = logging.INFO):
        self.log_path = log_path
        self.backup_days = backup_days
        self.level = level

    def configure(self, app) -> None:
        directory = os.path.dirname(self.log_path)
        os.makedirs(directory, exist_ok=True)
        handler = TimedRotatingFileHandler(
            self.log_path,
            when="D",
            interval=1,
            backupCount=self.backup_days,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
        handler.setFormatter(formatter)
        handler.utc = True
        app.logger.setLevel(self.level)
        app.logger.addHandler(handler)
        app.logger.propagate = False

        # Запись первой строки чтобы создать файл сразу
        app.logger.info("logger configured")

