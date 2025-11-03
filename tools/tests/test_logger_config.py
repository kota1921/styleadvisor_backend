import logging
import os
from flask import Flask
from tools.logger_config import TimedFileLoggerConfigurator


def test_logger_config_creates_file(tmp_path):
    app = Flask(__name__)
    log_file = tmp_path / "app.log"
    TimedFileLoggerConfigurator(log_path=str(log_file)).configure(app)
    app.logger.info("test")
    assert log_file.exists()
    assert os.path.getsize(log_file) > 0
    assert any(isinstance(h, logging.handlers.TimedRotatingFileHandler) for h in app.logger.handlers)

