from __future__ import annotations

import sys

from loguru import logger as _base_logger

_configured = False


def LoggerSetup(name: str) -> _base_logger.__class__:
    global _configured
    if not _configured:
        _base_logger.remove()
        _base_logger.add(
            sys.stderr,
            format=(
                "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level:<8} | "
                "{extra[module]:<20} | {message}"
            ),
            level="DEBUG",
        )
        _configured = True
    return _base_logger.bind(module=name)
