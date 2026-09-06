import re
from enum import StrEnum
from pathlib import Path

import pytest
from ai_business_radar_schemas.enums import (
    AIExtractionSourceType,
    AIExtractionStatus,
    AIExtractionTaskType,
    ChannelType,
    ClaimStatus,
    CollectionRunStatus,
    CollectionRunType,
    CollectionSourceType,
    DiscoveryMode,
    EvidenceSourceType,
    EvidenceType,
    MarketStage,
    OpportunitySignalRelationshipType,
    OpportunityStatus,
    QueryGroup,
    ReviewDecision,
    ReviewStatus,
    ReviewTargetType,
    ReviewType,
    SignalSourceType,
    SignalStatus,
    SignalType,
    TrendWindowType,
    UserRole,
    VideoProcessingStatus,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS = REPOSITORY_ROOT / "database/migrations"


ENUM_CONSTRAINTS: list[tuple[type[StrEnum], str]] = [
    (UserRole, "ck_user_profiles_role"),
    (DiscoveryMode, "ck_search_queries_discovery_mode"),
    (QueryGroup, "ck_search_queries_query_group"),
    (CollectionSourceType, "ck_collection_runs_source_type"),
    (CollectionRunType, "ck_collection_runs_run_type"),
    (CollectionRunStatus, "ck_collection_runs_status"),
    (ChannelType, "ck_channels_channel_type"),
    (VideoProcessingStatus, "ck_videos_processing_status"),
    (AIExtractionSourceType, "ck_ai_extractions_source_type"),
    (AIExtractionTaskType, "ck_ai_extractions_task_type"),
    (AIExtractionStatus, "ck_ai_extractions_status"),
    (SignalSourceType, "ck_signals_source_type"),
    (SignalType, "ck_signals_signal_type"),
    (ClaimStatus, "ck_signals_claim_status"),
    (SignalStatus, "ck_signals_status"),
    (MarketStage, "ck_opportunities_market_stage"),
    (OpportunityStatus, "ck_opportunities_status"),
    (
        OpportunitySignalRelationshipType,
        "ck_opportunity_signal_links_relationship_type",
    ),
    (EvidenceSourceType, "ck_opportunity_evidence_source_type"),
    (EvidenceType, "ck_opportunity_evidence_evidence_type"),
    (TrendWindowType, "ck_trend_snapshots_window_type"),
    (ReviewType, "ck_review_tasks_review_type"),
    (ReviewTargetType, "ck_review_tasks_target_type"),
    (ReviewStatus, "ck_review_tasks_status"),
    (ReviewDecision, "ck_review_tasks_decision"),
]


def constraint_section(sql: str, constraint_name: str) -> str:
    marker = f"CONSTRAINT {constraint_name}"
    marker_start = sql.rindex(marker)
    check_start = sql.index("CHECK", marker_start)
    open_parenthesis = sql.index("(", check_start)
    depth = 0
    in_string = False
    index = open_parenthesis

    while index < len(sql):
        character = sql[index]
        if character == "'":
            if in_string and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return sql[marker_start : index + 1]
        index += 1

    raise ValueError(f"Unbalanced CHECK constraint: {constraint_name}")


@pytest.mark.parametrize(("enum_type", "constraint_name"), ENUM_CONSTRAINTS)
def test_enum_values_exist_in_corresponding_database_check(
    enum_type: type[StrEnum], constraint_name: str
) -> None:
    migration_name = (
        "0009_opportunity_normalization.sql"
        if constraint_name == "ck_ai_extractions_source_type"
        else "0013_opportunity_activation.sql"
        if constraint_name == "ck_review_tasks_review_type"
        else "0001_initial_schema.sql"
    )
    sql = (MIGRATIONS / migration_name).read_text(encoding="utf-8")
    section = constraint_section(sql, constraint_name)
    python_values = {member.value for member in enum_type}
    sql_values = set(re.findall(r"'([^']+)'", section))
    assert python_values == sql_values, (
        f"{enum_type.__name__} differs from {constraint_name}: "
        f"python={sorted(python_values)}, sql={sorted(sql_values)}"
    )
