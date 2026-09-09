from uuid import uuid4

import pytest
from ai_business_radar_schemas.consolidation import OpportunityConsolidationOutput
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_business_radar_api.api.v1.consolidation import get_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.opportunity_consolidation import (
    DIMENSIONS,
    digest,
    validate_grounding,
)
from test_candidates import user


def unknown_output():
    return {
        **{
            k: {
                "text": None,
                "evidence_signal_ids": [],
                "information_class": "unknown",
                "support_level": "insufficient_evidence",
                "uncertainty": "No evidence",
            }
            for k in DIMENSIONS
        },
        "validation_gaps": ["Verify actual customer use"],
    }


def supported(identity, text="An attributed source observation"):
    return {
        "text": text,
        "evidence_signal_ids": [str(identity)],
        "information_class": "editorial_synthesis",
        "support_level": "partially_supported",
        "uncertainty": "Not independently verified",
    }


def signal(identity=None, **changes):
    return {
        "id": str(identity or uuid4()),
        "signal_type": "workflow",
        "evidence_role": "unknown",
        "claim_status": "creator_claim",
        "relationship_type": "supporting",
        "video_id": "v1",
        "channel_id": "c1",
        "business_model": None,
        "distribution_channels": None,
        **changes,
    }


def test_hash_is_deterministic_and_content_sensitive():
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    assert digest({"a": 2}) != digest({"a": 3})


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_unknown_fields_require_null_text(dimension):
    output = unknown_output()
    output[dimension]["text"] = "Invented commercial fact"
    with pytest.raises(ValidationError):
        OpportunityConsolidationOutput.model_validate(output)


def test_grounded_fields_need_owned_effective_references():
    evidence = signal()
    output = unknown_output()
    output["solution_pattern"] = supported(evidence["id"])
    parsed = OpportunityConsolidationOutput.model_validate(output)
    metadata = validate_grounding(parsed, {"signals": [evidence]})
    assert not metadata["solution_pattern"]["multi_video_coverage"]
    with pytest.raises(ValueError, match="outside"):
        validate_grounding(parsed, {"signals": []})
    output["solution_pattern"]["evidence_signal_ids"] = []
    with pytest.raises(ValidationError):
        OpportunityConsolidationOutput.model_validate(output)


@pytest.mark.parametrize(
    "dimension,kind,role",
    [
        ("revenue_summary", "pricing", "product_pricing"),
        ("revenue_summary", "revenue", "creator_monetization"),
        ("adoption_summary", "purchase_intent", "seller_cta"),
        ("adoption_summary", "adoption", "seller_cta"),
        ("distribution_summary", "product_launch", "seller_claim"),
        ("pricing_summary", "purchase_intent", "buyer_expression"),
        ("competition_summary", "technology", "unknown"),
        ("business_model_summary", "technology", "unknown"),
    ],
)
def test_commercial_roles_cannot_cross_dimensions(dimension, kind, role):
    evidence = signal(signal_type=kind, evidence_role=role)
    output = unknown_output()
    output[dimension] = supported(evidence["id"])
    with pytest.raises(ValueError, match="dimension-appropriate"):
        validate_grounding(
            OpportunityConsolidationOutput.model_validate(output), {"signals": [evidence]}
        )


def test_real_buyer_comment_is_not_pricing_or_revenue():
    evidence = signal(signal_type="purchase_intent", evidence_role="buyer_expression")
    output = OpportunityConsolidationOutput.model_validate(unknown_output())
    validate_grounding(output, {"signals": [evidence]})
    assert output.pricing_summary.text is None and output.revenue_summary.text is None


def test_multi_video_is_dimension_specific_and_contradictions_required():
    first = signal()
    second = signal(video_id="v2", channel_id="c2", relationship_type="contradicting")
    output = unknown_output()
    output["solution_pattern"] = supported(first["id"])
    with pytest.raises(ValueError, match="omitted"):
        validate_grounding(
            OpportunityConsolidationOutput.model_validate(output), {"signals": [first, second]}
        )
    output["solution_pattern"]["evidence_signal_ids"].append(second["id"])
    result = validate_grounding(
        OpportunityConsolidationOutput.model_validate(output), {"signals": [first, second]}
    )
    assert not result["solution_pattern"]["multi_video_coverage"]
    second["relationship_type"] = "supporting"
    result = validate_grounding(
        OpportunityConsolidationOutput.model_validate(output), {"signals": [first, second]}
    )
    assert result["solution_pattern"]["multi_video_coverage"]
    assert not result["problem_summary"]["multi_video_coverage"]


@pytest.mark.parametrize(
    "phrase",
    ["Total addressable market is huge", "Market size is $1B", "Multi-source corroborated"],
)
def test_market_size_and_corroboration_are_rejected(phrase):
    evidence = signal()
    output = unknown_output()
    output["solution_pattern"] = supported(evidence["id"], phrase)
    with pytest.raises(ValueError, match="market sizing"):
        validate_grounding(
            OpportunityConsolidationOutput.model_validate(output), {"signals": [evidence]}
        )


def test_admin_authority_all_business_case_mutations():
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_service] = lambda: object()
    identity, case_id = uuid4(), uuid4()
    base = f"/api/v1/admin/opportunities/{identity}"
    with TestClient(app) as client:
        assert client.get(f"{base}/consolidation/current").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user("user")
        for method, path in [
            ("get", "/consolidation/current"),
            ("get", "/consolidations"),
            ("post", "/consolidation"),
            ("post", f"/consolidations/{case_id}/approve"),
            ("post", f"/consolidations/{case_id}/accept"),
            ("get", "/consolidation/evidence/problem_summary"),
        ]:
            assert getattr(client, method)(base + path).status_code == 403
