import re
from pathlib import Path

from ai_business_radar_api.infrastructure.database.models import Base

MIGRATION = Path(__file__).parents[3] / "database/migrations/0001_initial_schema.sql"


def test_all_migrated_tables_have_exactly_one_model() -> None:
    migrated = set(re.findall(r"^CREATE TABLE (\w+)", MIGRATION.read_text(), re.MULTILINE))
    assert set(Base.metadata.tables) == migrated
    assert len(migrated) == 18


def test_critical_columns_remain_mapped() -> None:
    expected = {
        "channels": {"youtube_channel_id", "first_seen_at", "last_seen_at"},
        "ai_extractions": {"source_id", "input_hash", "raw_output", "parsed_output"},
        "signals": {"source_id", "claim_status", "confidence"},
        "opportunity_scores": {"scoring_version", "inputs_snapshot"},
    }
    for table_name, columns in expected.items():
        assert columns <= set(Base.metadata.tables[table_name].columns.keys())
