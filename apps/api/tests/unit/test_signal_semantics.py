from types import SimpleNamespace

import pytest

from ai_business_radar_api.services.signal_semantics import decision_hash, evaluate


@pytest.mark.parametrize(
    "kind,text,decision,role",
    [
        ("purchase_intent", "Buy now", "reject_semantic", "seller_cta"),
        ("purchase_intent", "Book now", "reject_semantic", "seller_cta"),
        ("purchase_intent", "Call us", "reject_semantic", "seller_cta"),
        ("purchase_intent", "Pre-order here", "reject_semantic", "seller_cta"),
        ("purchase_intent", "Pre-order now.", "reject_semantic", "seller_cta"),
        ("purchase_intent", "Limited slots available", "reject_semantic", "seller_cta"),
        ("purchase_intent", "I bought one", "accept", "buyer_expression"),
        ("purchase_intent", "I ordered it despite the price", "accept", "buyer_expression"),
        ("purchase_intent", "I'd pay for this", "accept", "buyer_expression"),
        ("purchase_intent", "Where can I buy this?", "accept", "buyer_expression"),
        ("purchase_intent", "We are looking for a tool like this", "accept", "buyer_expression"),
        ("purchase_intent", "We signed up", "accept", "buyer_expression"),
        ("purchase_intent", "Preordered mine and waiting", "accept", "buyer_expression"),
        (
            "purchase_intent",
            "Price with shipping is $508. I still ordered one. It's so cool!",
            "accept",
            "buyer_expression",
        ),
        ("purchase_intent", "I did not buy one", "review", "unknown"),
        ("purchase_intent", "I would not pay for this", "review", "unknown"),
        ("purchase_intent", "If I ordered this, I would need a PC", "review", "unknown"),
        ("purchase_intent", "I bought one. Buy now with my link", "review", "unknown"),
        ("purchase_intent", "$499 pre-order", "review", "product_pricing"),
        ("purchase_intent", "When will it launch?", "review", "unknown"),
        (
            "revenue",
            "As an Amazon Associate I earn from qualifying purchases",
            "reject_semantic",
            "creator_monetization",
        ),
        ("revenue", "Creator affiliate commission", "reject_semantic", "creator_monetization"),
        ("revenue", "YouTube ad revenue", "reject_semantic", "creator_monetization"),
        ("revenue", "Creator referral income", "reject_semantic", "creator_monetization"),
        ("revenue", "Sponsored-video payment", "reject_semantic", "creator_monetization"),
        (
            "distribution",
            "As an Amazon Associate I earn from qualifying purchases",
            "accept",
            "creator_monetization",
        ),
        ("revenue", "Product X generated $2 million in sales", "accept", "product_monetization"),
        ("revenue", "Product X raised $2 million", "review", "third_party_observation"),
        (
            "revenue",
            "Product X forecast $2 million in revenue",
            "review",
            "third_party_observation",
        ),
        ("revenue", "A $10 billion business", "review", "unknown"),
        ("pricing", "$499 pre-order", "accept", "product_pricing"),
        ("pricing", "A free tier is available", "accept", "product_pricing"),
        ("pricing", "An affordable tool", "review", "unknown"),
        ("adoption", "Pre-order now", "reject_semantic", "seller_cta"),
        ("adoption", "I ordered one", "accept", "observed_transaction"),
        ("adoption", "I want one", "review", "unknown"),
        ("adoption", "500 clinics use Product X", "accept", "seller_claim"),
        ("adoption", "It answers phone calls", "review", "unknown"),
        ("workflow", "It answers phone calls", "accept", "unknown"),
        ("pain", "Clinics miss incoming calls", "accept", "unknown"),
    ],
)
def test_semantic_decisions(kind, text, decision, role):
    result = evaluate(kind, text, text)
    assert (result.decision, result.evidence_role) == (decision, role)


def test_excerpt_does_not_upgrade_price_only_statement():
    decision = evaluate(
        "purchase_intent",
        "The commenter states the product price is $508.",
        "Price with shipping is $508. I still ordered one.",
    )
    assert decision.decision == "review"


def test_identity_requires_claim_and_commercial_context():
    values = dict(statement="Same", evidence_text="Same", source_id="same", signal_type="pricing")
    assert decision_hash(SimpleNamespace(**values, claim_status="fact")) != decision_hash(
        SimpleNamespace(**values, claim_status="creator_claim")
    )
    assert decision_hash(SimpleNamespace(**values, customer_type="A")) != decision_hash(
        SimpleNamespace(**values, customer_type="B")
    )


def test_price_statement_not_upgraded_by_other_buying_sentence():
    result = evaluate(
        "purchase_intent",
        "Considers the product worth $400.",
        "It is worth 400. If I can get one from Amazon I will have one.",
    )
    assert result.decision == "review"


def test_mixed_product_sales_and_creator_income_routes_review():
    text = "Product X generated $2 million in sales; I also earn affiliate commission."
    assert evaluate("revenue", text, text).decision == "review"
