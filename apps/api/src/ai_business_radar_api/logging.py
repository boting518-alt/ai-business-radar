"""Minimal standard-library logging configuration."""

import logging


def configure_logging(level: str) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx INFO records include full request URLs; provider URLs may contain API
    # keys in query parameters (for example the YouTube Data API).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
