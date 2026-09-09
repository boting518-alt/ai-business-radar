"""Dramatiq CLI entry module with fail-fast, observable configuration."""

import logging

from ai_business_radar_api.logging import configure_logging
from ai_business_radar_api.runtime_config import log_runtime_target

from .broker import initialize_broker
from .config import WorkerSettings

settings = WorkerSettings()
configure_logging(settings.log_level)
log_runtime_target(logging.getLogger(__name__), "worker", settings.runtime_target)
broker = initialize_broker(settings)

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
from .actors.consolidation import consolidate_opportunity  # noqa: E402

__all__ = [
    "consolidate_opportunity",
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
