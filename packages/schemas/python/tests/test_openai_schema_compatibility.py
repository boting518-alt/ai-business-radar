import json
from collections.abc import Iterator
from typing import Any

import pytest
from ai_business_radar_schemas.ai_outputs import (
    AI_OUTPUT_MODELS,
    BusinessSignalExtractorOutput,
    CommentPainMinerOutput,
    HypeDetectorOutput,
    OpportunityNormalizerOutput,
    RelevanceFilterOutput,
)

LOOKAROUND_MARKERS = ("(?=", "(?!", "(?<=", "(?<!")


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def numeric_variant(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "number":
        return schema
    variants = schema.get("anyOf", [])
    return next(item for item in variants if item.get("type") == "number")


@pytest.mark.parametrize("task_name", sorted(AI_OUTPUT_MODELS))
def test_ai_schema_has_no_unsupported_regex_or_decimal_fallback(task_name: str) -> None:
    schema = AI_OUTPUT_MODELS[task_name].model_json_schema(mode="validation")
    serialized = json.dumps(schema, sort_keys=True)
    assert not any(marker in serialized for marker in LOOKAROUND_MARKERS)
    assert all("pattern" not in node for node in walk(schema))
    assert not any(
        {item.get("type") for item in node.get("anyOf", [])} >= {"number", "string"}
        for node in walk(schema)
    )


@pytest.mark.parametrize(
    ("schema", "minimum", "maximum"),
    [
        (RelevanceFilterOutput.model_json_schema()["properties"]["relevance_score"], 0, 1),
        (OpportunityNormalizerOutput.model_json_schema()["properties"]["confidence"], 0, 1),
        (HypeDetectorOutput.model_json_schema()["properties"]["content_hype_score"], 0, 100),
        (HypeDetectorOutput.model_json_schema()["properties"]["real_demand_score"], 0, 100),
        (
            CommentPainMinerOutput.model_json_schema()["$defs"]["CommentPainSignal"][
                "properties"
            ]["evidence_strength"],
            0,
            1,
        ),
        (
            BusinessSignalExtractorOutput.model_json_schema()["$defs"][
                "ExtractedBusinessSignal"
            ]["properties"]["confidence"],
            0,
            1,
        ),
    ],
)
def test_ai_bounded_numbers_use_plain_json_number_schema(
    schema: dict[str, Any], minimum: int, maximum: int
) -> None:
    number = numeric_variant(schema)
    assert number["type"] == "number"
    assert number["minimum"] == minimum
    assert number["maximum"] == maximum
    assert "pattern" not in number


def test_optional_ai_amounts_are_nullable_non_negative_numbers() -> None:
    signal_schema = BusinessSignalExtractorOutput.model_json_schema()
    price = signal_schema["$defs"]["AIPriceRange"]["properties"]
    comment = CommentPainMinerOutput.model_json_schema()["$defs"]["CommentPainSignal"][
        "properties"
    ]
    for schema in (price["min"], price["max"], comment["spend"]):
        assert numeric_variant(schema)["minimum"] == 0
        assert {item["type"] for item in schema["anyOf"]} == {"number", "null"}
    assert comment["purchase_intent"]["type"] == "boolean"


def test_ai_runtime_numbers_are_floats_and_keep_frozen_bounds() -> None:
    relevance = RelevanceFilterOutput(
        relevant=True,
        relevance_score="0.75",
        content_type=None,
        primary_topic=None,
        reason="Relevant",
    )
    assert relevance.relevance_score == 0.75
    assert isinstance(relevance.relevance_score, float)

    with pytest.raises(ValueError):
        RelevanceFilterOutput(
            relevant=True,
            relevance_score=1.01,
            content_type=None,
            primary_topic=None,
            reason="Invalid",
        )


def test_ai_price_range_preserves_cross_field_validation() -> None:
    with pytest.raises(ValueError, match="less than or equal"):
        BusinessSignalExtractorOutput(
            industry=None,
            customer=None,
            problem=None,
            solution=None,
            business_model=None,
            technology=[],
            distribution=[],
            pricing={"min": 20.25, "max": 10.5, "currency": "USD", "period": "month"},
            signals=[],
        )
