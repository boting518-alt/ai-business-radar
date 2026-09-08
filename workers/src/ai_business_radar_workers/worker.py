"""Dramatiq CLI entry module; constructs the Redis broker before actor imports."""

from .broker import initialize_broker

broker = initialize_broker()

from .actors import (  # noqa: E402
    reconcile_translation_coverage,
    recover_stale_collection_claims,
    recover_stale_discovery_runs,
    run_comment_pain_mining,
    run_opportunity_normalization,
    run_opportunity_scoring,
    run_relevance_filter,
    run_signal_extraction,
    run_trend_aggregation,
    run_youtube_comment_collection,
    run_youtube_discovery,
    run_youtube_metadata_collection,
    translate_batch,
    translate_opportunity,
    translate_signal,
)

__all__ = [
    "broker",
    "recover_stale_collection_claims",
    "recover_stale_discovery_runs",
    "reconcile_translation_coverage",
    "translate_batch",
    "translate_opportunity",
    "translate_signal",
    "run_comment_pain_mining",
    "run_relevance_filter",
    "run_opportunity_normalization",
    "run_opportunity_scoring",
    "run_signal_extraction",
    "run_trend_aggregation",
    "run_youtube_comment_collection",
    "run_youtube_discovery",
    "run_youtube_metadata_collection",
]
