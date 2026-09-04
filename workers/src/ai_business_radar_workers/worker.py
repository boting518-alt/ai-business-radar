"""Dramatiq CLI entry module; constructs the Redis broker before actor imports."""

from .broker import initialize_broker

broker = initialize_broker()

from .actors import (  # noqa: E402
    recover_stale_collection_claims,
    run_youtube_comment_collection,
    run_youtube_discovery,
    run_youtube_metadata_collection,
)

__all__ = [
    "broker",
    "recover_stale_collection_claims",
    "run_youtube_comment_collection",
    "run_youtube_discovery",
    "run_youtube_metadata_collection",
]
