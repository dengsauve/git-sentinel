"""Logging configuration helpers."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any


def configure_logging(verbose: bool = False) -> None:
    """Configure application logging."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s %(levelname)s %(name)s "
            "repository=%(repository)s operation=%(operation)s %(message)s"
        ),
    )


class ContextLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Ensure expected structured fields are always present."""

    def process(
        self,
        msg: str,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[str, MutableMapping[str, Any]]:
        raw_extra = kwargs.get("extra")
        extra: dict[str, Any]
        if isinstance(raw_extra, MutableMapping):
            extra = dict(raw_extra)
        else:
            extra = {}
        extra.setdefault("repository", "-")
        extra.setdefault("operation", "-")
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> ContextLoggerAdapter:
    """Return a logger adapter with stable default fields."""

    return ContextLoggerAdapter(logging.getLogger(name), {})
