from decimal import Decimal

SCORING_VERSION = "score-v001"
SCORE_QUANTUM = Decimal("0.01")
COMPONENT_WEIGHTS = {
    "trend_velocity_score": Decimal("0.20"),
    "demand_evidence_score": Decimal("0.20"),
    "revenue_evidence_score": Decimal("0.15"),
    "pain_severity_score": Decimal("0.15"),
    "competition_white_space_score": Decimal("0.10"),
    "build_feasibility_score": Decimal("0.10"),
    "distribution_ease_score": Decimal("0.10"),
}
CLAIM_WEIGHTS = {
    "fact": Decimal("1.00"),
    "creator_claim": Decimal("0.40"),
    "inferred": Decimal("0.20"),
    "opinion": Decimal("0.10"),
    "speculation": Decimal("0.05"),
    "unknown": Decimal("0.20"),
}
WHITE_SPACE_CURVE = (
    (Decimal(0), Decimal(55)),
    (Decimal(25), Decimal(85)),
    (Decimal(45), Decimal(100)),
    (Decimal(70), Decimal(65)),
    (Decimal(100), Decimal(20)),
)
