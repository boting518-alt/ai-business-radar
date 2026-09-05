from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from ai_business_radar_schemas import BusinessSignalExtractorOutput, CommentPainMinerOutput

from ai_business_radar_api.services.comment_pain_mining import CommentPainMiningService
from ai_business_radar_api.services.signal_extraction import BusinessSignalExtractionService


def test_signal_transport_floats_map_explicitly_to_domain_decimals() -> None:
    parsed = BusinessSignalExtractorOutput(
        industry="Healthcare",
        customer="Dental practices",
        problem="Missed calls",
        solution="AI receptionist",
        business_model="SaaS",
        technology=["voice AI"],
        distribution=["direct sales"],
        pricing={"min": 99.95, "max": 299.5, "currency": "USD", "period": "month"},
        signals=[
            {
                "type": "pricing",
                "statement": "The product has a monthly price.",
                "evidence": "Pricing is stated in the source.",
                "claim_status": "creator_claim",
                "confidence": 0.82,
            }
        ],
    )
    values = BusinessSignalExtractionService._signal_values(
        SimpleNamespace(id=uuid4(), published_at=datetime.now(UTC)),
        uuid4(),
        parsed,
        parsed.signals[0],
        datetime.now(UTC),
    )
    assert values["confidence"] == Decimal("0.82")
    assert values["price_min"] == Decimal("99.95")
    assert values["price_max"] == Decimal("299.5")


def test_comment_transport_float_maps_explicitly_to_domain_decimal() -> None:
    parsed = CommentPainMinerOutput(
        signals=[
            {
                "category": "existing pain",
                "pain": "Calls are repeatedly missed.",
                "current_solution": None,
                "requested_solution": "Automated answering",
                "spend": 49.95,
                "purchase_intent": True,
                "evidence_strength": 0.73,
                "comment_id": uuid4(),
            }
        ]
    )
    item = parsed.signals[0]
    values = CommentPainMiningService._build_signal_values(
        SimpleNamespace(id=item.comment_id, published_at=datetime.now(UTC), text="Evidence"),
        uuid4(),
        item,
        "pain",
        datetime.now(UTC),
    )
    assert values["confidence"] == Decimal("0.73")
    assert values["evidence_strength"] == Decimal("0.73")
