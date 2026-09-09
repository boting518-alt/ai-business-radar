import re
from pathlib import Path

from ai_business_radar_api.infrastructure.database.models import Base

MIGRATIONS = Path(__file__).parents[3] / "database/migrations"


def test_all_migrated_tables_have_exactly_one_model() -> None:
    migration_sql = "\n".join(path.read_text() for path in sorted(MIGRATIONS.glob("[0-9]*.sql")))
    migrated = set(re.findall(r"^CREATE TABLE (\w+)", migration_sql, re.MULTILINE))
    assert set(Base.metadata.tables) == migrated
    assert len(migrated) == 32


def test_critical_columns_remain_mapped() -> None:
    expected = {
        "channels": {"youtube_channel_id", "first_seen_at", "last_seen_at"},
        "ai_extractions": {"source_id", "signal_id", "input_hash", "raw_output", "parsed_output"},
        "signals": {"source_id", "claim_status", "confidence"},
        "opportunity_scores": {"scoring_version", "input_hash", "inputs_snapshot"},
        "trend_snapshots": {"aggregation_version", "window_type", "momentum_score"},
        "youtube_discovery_items": {
            "collection_run_id",
            "search_query_id",
            "youtube_video_id",
            "processing_status",
            "claimed_at",
            "canonical_video_id",
            "processed_at",
            "error_summary",
        },
        "comments": {"source_updated_at"},
        "review_tasks": {"context", "resolved_by"},
    }
    for table_name, columns in expected.items():
        assert columns <= set(Base.metadata.tables[table_name].columns.keys())
