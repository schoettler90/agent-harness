import os
import sys

from dotenv import load_dotenv
from loguru import logger as _base_logger
from loguru._logger import Logger

load_dotenv()

_configured = False
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()


def LoggerSetup(name: str) -> Logger:
    global _configured
    if not _configured:
        _base_logger.remove()
        _base_logger.add(
            sys.stdout,
            level=LOG_LEVEL,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level}</level> | "
                "<cyan>{extra[logger_tag]}</cyan> | "
                "<level>{message}</level>"
            ),
        )
        _configured = True
    return _base_logger.bind(logger_tag=name)
