"""Conservative, versioned commercial-role guardrails; no model calls or type rewrites."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..infrastructure.database.models import AIExtraction, ReviewTask, Signal
from ..infrastructure.database.models.fact import SignalSemanticAudit

GUARDRAIL_VERSION = "semantic-v001"
RISK_TYPES = ("purchase_intent", "revenue", "adoption", "pricing")


def matches(pattern, value):
    return bool(re.search(pattern, value, re.I))


@dataclass(frozen=True)
class SemanticDecision:
    decision: str = "accept"
    reason: str = "no_semantic_conflict"
    actor_role: str = "unknown"
    evidence_role: str = "unknown"

    @property
    def semantic_status(self):
        return {
            "accept": "current",
            "review": "under_review",
            "reject_semantic": "invalid_semantic",
        }[self.decision]


def evaluate(signal_type: str, statement: str, evidence: str | None) -> SemanticDecision:
    """Only individual evidence cues; no whole-video boilerplate or confidence shortcuts."""
    e = (evidence or "").replace("’", "'").lower()
    s = statement.replace("’", "'").lower()
    both = s + " " + e
    buyer = matches(
        r"\b(?:i|we)\s+(?:(?:have|already|still|just)\s+)*(?:bought|ordered"
        r"|pre-?ordered|signed up|want (?:one|this)|would pay|will buy"
        r"|are looking for|need a tool)|\bi'd pay\b|\bwhere can i buy\b"
        r"|\bpre-?ordered mine\b|\bi'm getting one\b|\bi will have one\b",
        e,
    )
    transaction = matches(
        r"\b(?:i|we)\s+(?:(?:have|already|still|just)\s+)*"
        r"(?:bought|ordered|pre-?ordered|signed up|use|are using)\b|\bpre-?ordered mine\b",
        e,
    )
    negative = matches(
        r"\b(?:would not|wouldn't|will not|won't|did not|didn't|never|not going to)\b"
        r"|\bif i (?:bought|ordered)\b",
        e,
    )
    cta = matches(
        r"\b(?:buy|book|order|pre-?order)\s+(?:now|here|today)\b|\bcall (?:us"
        r"|ai connect pro)\b|\blimited slots\b|\b(?:creator|description|seller"
        r"|vendor)\b.{0,45}\b(?:invites|encourages)\b",
        both,
    )
    affiliate = matches(
        r"amazon associate|affiliate (?:commission|income|revenue|link|disclosure)"
        r"|earn.{0,25}qualifying purchases|referral income|youtube ad revenue"
        r"|sponsored.video (?:payment|income)",
        both,
    )
    creator_money = affiliate or matches(
        r"(?:creator|channel).{0,35}(?:earns|income|monetiz|commission|sponsorship)", both
    )
    price = matches(
        r"(?:[$€£₹]\s*[\d,]+|\b\d+(?:\.\d+)?\s*(?:usd|dollars|eur)\b|\bfree (?:plan|tier)\b)", e
    )
    if creator_money:
        actor = "affiliate_referrer" if affiliate else "creator_channel"
        if signal_type == "revenue":
            return SemanticDecision(
                "review"
                if buyer or (price and matches(r"\b(?:sales|revenue|arr|mrr)\b", e))
                else "reject_semantic",
                "affiliate_revenue_not_product_revenue"
                if affiliate
                else "creator_monetization_scope",
                actor,
                "creator_monetization",
            )
        if signal_type in {"pricing", "adoption", "purchase_intent"}:
            return SemanticDecision(
                "review", "creator_monetization_scope", actor, "creator_monetization"
            )
        return SemanticDecision(
            "accept", "creator_monetization_scope", actor, "creator_monetization"
        )
    if signal_type == "purchase_intent":
        if matches(r"\b(?:price|worth|costs?)\b", s) and not matches(
            r"\b(?:ordered|bought|buy|purchase|intent|desire|willingness|want)\b", s
        ):
            return SemanticDecision(
                "review", "price_without_buyer_intent", "unknown", "product_pricing"
            )
        if buyer and not negative and not cta:
            return SemanticDecision(
                "accept", "explicit_buyer_expression", "buyer", "buyer_expression"
            )
        if cta and not buyer:
            return SemanticDecision(
                "reject_semantic", "seller_cta_not_purchase_intent", "seller_vendor", "seller_cta"
            )
        if price and not buyer:
            return SemanticDecision(
                "review", "price_without_buyer_intent", "unknown", "product_pricing"
            )
        return SemanticDecision("review", "ambiguous_actor", "unknown", "unknown")
    if signal_type == "adoption":
        if cta and not buyer:
            return SemanticDecision(
                "reject_semantic", "seller_cta_not_adoption", "seller_vendor", "seller_cta"
            )
        if transaction and not negative:
            return SemanticDecision(
                "accept", "observed_buyer_action", "buyer", "observed_transaction"
            )
        if matches(
            r"\b(?:sold|purchased)\s+(?:over |more than )?[\d,]+|\b[\d,]+\s+(?:clinics"
            r"|customers|users|teams)\s+(?:use|using|have|adopted)",
            e,
        ):
            return SemanticDecision(
                "accept", "attributed_adoption_claim", "featured_product_company", "seller_claim"
            )
        return SemanticDecision("review", "unverified_adoption_scope")
    if signal_type == "revenue":
        if matches(r"\b(?:raised|funding|valuation|guided|guides|forecast|projected)\b", both):
            return SemanticDecision(
                "review", "non_realized_revenue_scope", "unknown", "third_party_observation"
            )
        if matches(r"\b(?:sales|revenue|arr|mrr)\b", e) and price:
            return SemanticDecision(
                "accept",
                "attributed_product_revenue",
                "featured_product_company",
                "product_monetization",
            )
        return SemanticDecision("review", "ambiguous_revenue_owner")
    if signal_type == "pricing":
        if price:
            return SemanticDecision(
                "accept",
                "explicit_product_price",
                "buyer" if buyer else "featured_product_company",
                "product_pricing",
            )
        return SemanticDecision("review", "price_not_explicit")
    if cta:
        return SemanticDecision("accept", "seller_cta_context_only", "seller_vendor", "seller_cta")
    return SemanticDecision()


def evaluate_signal(signal):
    return evaluate(signal.signal_type, signal.statement, signal.evidence_text)


def decision_hash(signal):
    fields = (
        "source_type",
        "source_id",
        "signal_type",
        "statement",
        "evidence_text",
        "claim_status",
        "industry",
        "customer_type",
        "problem",
        "solution",
        "business_model",
        "price_min",
        "price_max",
        "price_currency",
        "price_period",
        "revenue_claim_amount",
        "revenue_claim_currency",
        "revenue_claim_period",
        "customer_count_claim",
        "technology",
        "distribution_channels",
        "geography",
    )
    values = {key: getattr(signal, key, None) for key in fields}
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


async def exact_current_duplicate(session, signal):
    if not signal.ai_extraction_id or not signal.evidence_text:
        return None
    extraction = await session.get(AIExtraction, signal.ai_extraction_id)
    if not extraction or extraction.task_type not in {"signal_extractor", "comment_pain_miner"}:
        return None
    rows = await session.scalars(
        select(Signal)
        .join(AIExtraction, AIExtraction.id == Signal.ai_extraction_id)
        .where(
            Signal.id != signal.id,
            Signal.source_type == signal.source_type,
            Signal.source_id == signal.source_id,
            Signal.signal_type == signal.signal_type,
            Signal.statement == signal.statement,
            Signal.evidence_text == signal.evidence_text,
            Signal.status == "active",
            Signal.semantic_status == "current",
            Signal.ai_extraction_id != signal.ai_extraction_id,
            AIExtraction.task_type == extraction.task_type,
            AIExtraction.status == "completed",
        )
        .order_by(Signal.created_at, Signal.id)
    )
    for other in rows:
        if (
            (
                signal.status != "active"
                or (other.created_at, str(other.id)) < (signal.created_at, str(signal.id))
            )
            and decision_hash(other) == decision_hash(signal)
            and evaluate_signal(other).decision == "accept"
        ):
            return other
    return None


async def persist_decision(session, signal, decision=None, *, duplicate=None, operator_note=None):
    decision = decision or evaluate_signal(signal)
    status = "superseded" if duplicate else decision.semantic_status
    reason = "duplicate_current_evidence" if duplicate else decision.reason
    fingerprint = decision_hash(signal)
    values = dict(
        signal_id=signal.id,
        guardrail_version=GUARDRAIL_VERSION,
        guardrail_decision=decision.decision,
        guardrail_reason_code=reason,
        original_signal_type=signal.signal_type,
        canonical_signal_type=signal.signal_type,
        actor_role=decision.actor_role,
        evidence_role=decision.evidence_role,
        previous_semantic_status=signal.semantic_status,
        semantic_status=status,
        superseded_by=duplicate.id if duplicate else None,
        input_hash=fingerprint,
        operator_note=operator_note,
    )
    result = await session.execute(
        insert(SignalSemanticAudit)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(SignalSemanticAudit.id)
    )
    if result.scalar_one_or_none() is None:
        return False
    signal.semantic_status = status
    signal.actor_role = decision.actor_role
    signal.evidence_role = decision.evidence_role
    signal.guardrail_version = GUARDRAIL_VERSION
    signal.guardrail_decision = decision.decision
    signal.guardrail_reason_code = reason
    signal.superseded_by = duplicate.id if duplicate else None
    signal.updated_at = datetime.now(UTC)
    if status in {"under_review", "invalid_semantic"}:
        # Reuse the existing open-task unique key. Context is explanatory, never an override.
        await session.execute(
            insert(ReviewTask)
            .values(
                review_type="signal_validation",
                target_type="signal",
                target_id=signal.id,
                status="pending",
                priority=1,
                context={
                    "semantic_guardrail": asdict(decision),
                    "semantic_status": status,
                    "guardrail_version": GUARDRAIL_VERSION,
                },
            )
            .on_conflict_do_nothing()
        )
    await session.flush()
    return True


async def guard_created(session, signals):
    for signal in signals:
        await persist_decision(session, signal)
    return signals
