from ai_business_radar_schemas import OpportunitySummary, SignalExtractionCandidate
from ai_business_radar_schemas.enums import ClaimStatus, MarketStage, SignalType


def test_backend_imports_canonical_shared_schemas() -> None:
    assert SignalType.PAIN.value == "pain"
    assert MarketStage.EMERGING.value == "emerging"
    assert ClaimStatus.CREATOR_CLAIM.value == "creator_claim"
    assert SignalExtractionCandidate.__module__.startswith("ai_business_radar_schemas")
    assert OpportunitySummary.__module__.startswith("ai_business_radar_schemas")
