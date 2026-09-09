"""Versioned editorial synthesis. No read path generates AI or edits canonical fields."""

import asyncio
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from ai_business_radar_schemas.consolidation import OpportunityConsolidationOutput
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from ..infrastructure.ai import resolve_prompt
from ..infrastructure.ai.errors import AIStructuredOutputError
from ..infrastructure.database.models import (
    Comment,
    Opportunity,
    OpportunityConsolidation,
    OpportunityRevision,
    OpportunitySignalLink,
    Signal,
    Video,
)
from ..infrastructure.database.repositories.radar_queries import RadarQueryRepository
from .candidate_workspace import CandidateConflict, CandidateNotFound

FAMILY = "opportunity-consolidation"
DIMENSIONS = tuple(k for k in OpportunityConsolidationOutput.model_fields if k != "validation_gaps")
PROPOSAL_FIELDS = {
    "problem_summary": "problem",
    "solution_pattern": "solution",
    "workflow_summary": "one_line_thesis",
    "business_model_summary": "business_model",
}
CONTEXT_FIELDS = (
    "name",
    "industry",
    "customer_type",
    "one_line_thesis",
    "problem",
    "solution",
    "business_model",
)
SIGNAL_FIELDS = (
    "id",
    "signal_type",
    "statement",
    "evidence_text",
    "claim_status",
    "actor_role",
    "evidence_role",
    "source_type",
    "source_id",
    "comment_id",
    "observed_at",
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
    "distribution_channels",
    "technology",
)


def canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def digest(value):
    return sha256(
        json.dumps(canonical(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class AcceptProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: str
    expected_updated_at: datetime
    edited_text: str | None = Field(None, min_length=1, max_length=3000)
    note: str = Field(min_length=1, max_length=2000)


def validate_grounding(output, bundle):
    """Reject foreign IDs and role/category errors; never promise semantic entailment."""
    signals = {s["id"]: s for s in bundle["signals"]}
    metadata = {}
    for name in DIMENSIONS:
        field = getattr(output, name)
        ids = [str(i) for i in field.evidence_signal_ids]
        if any(i not in signals for i in ids):
            raise ValueError("Evidence reference is outside the effective input bundle")
        cited = [signals[i] for i in ids]
        supported = field.support_level in {"supported", "partially_supported"}
        eligible = {
            "pricing_summary": lambda s: (
                s["signal_type"] == "pricing"
                and s["evidence_role"] in {"product_pricing", "observed_transaction"}
            ),
            "revenue_summary": lambda s: (
                s["signal_type"] == "revenue"
                and s["evidence_role"] in {"product_monetization", "observed_transaction"}
            ),
            "adoption_summary": lambda s: (
                s["signal_type"] == "adoption"
                and s["evidence_role"] not in {"seller_cta", "creator_monetization"}
            ),
            "distribution_summary": lambda s: (
                s["signal_type"] == "distribution" or bool(s["distribution_channels"])
            ),
            "competition_summary": lambda s: s["signal_type"] == "competition",
            "business_model_summary": lambda s: (
                bool(s["business_model"])
                or s["evidence_role"]
                in {"product_monetization", "product_pricing", "observed_transaction"}
            ),
        }.get(name)
        if supported and eligible and not any(eligible(s) for s in cited):
            raise ValueError(f"No dimension-appropriate evidence for {name}")
        if name == "revenue_summary" and any(
            s["evidence_role"] == "creator_monetization" for s in cited
        ):
            raise ValueError("Creator monetization cannot support product revenue")
        if (
            name
            in {"pricing_summary", "revenue_summary", "adoption_summary", "distribution_summary"}
            and field.support_level == "hypothesis"
        ):
            raise ValueError(
                "Commercial quantities/channels/adoption must remain unknown when unsupported"
            )
        if field.text and any(
            t in field.text.lower()
            for t in ("total addressable market", "market size", "multi-source corroborated")
        ):
            raise ValueError("Unsupported market sizing or corroboration claim")
        conflicts = [s["id"] for s in cited if s["relationship_type"] == "contradicting"]
        if conflicts and not field.uncertainty:
            raise ValueError("Contradicting references require explicit uncertainty")
        videos = sorted(
            {
                s["video_id"]
                for s in cited
                if s["video_id"] and s["relationship_type"] == "supporting"
            }
        )
        channels = sorted({s["channel_id"] for s in cited if s["channel_id"]})
        metadata[name] = {
            "video_count": len(videos),
            "channel_count": len(channels),
            "multi_video_coverage": len(videos) >= 2,
            "claim_statuses": dict(Counter(s["claim_status"] for s in cited)),
            "contradicting_signal_ids": conflicts,
        }
    # All contradictions must be acknowledged somewhere, not silently dropped from the case.
    contradictions = {
        s["id"] for s in signals.values() if s["relationship_type"] == "contradicting"
    }
    referenced = {str(i) for k in DIMENSIONS for i in getattr(output, k).evidence_signal_ids}
    if not contradictions <= referenced:
        raise ValueError("Contradicting evidence omitted")
    return metadata


class OpportunityConsolidationService:
    def __init__(self, sessions, enqueuer=None):
        self.sessions = sessions
        self.enqueuer = enqueuer

    async def bundle(self, session, opportunity):
        rows = (
            await session.execute(
                select(Signal, OpportunitySignalLink.relationship_type, Video.id, Video.channel_id)
                .join(OpportunitySignalLink, OpportunitySignalLink.signal_id == Signal.id)
                .outerjoin(Comment, Comment.id == Signal.comment_id)
                .outerjoin(Video, Video.id == func.coalesce(Signal.video_id, Comment.video_id))
                .where(OpportunitySignalLink.opportunity_id == opportunity.id)
                .order_by(Signal.id)
            )
        ).all()
        effective = []
        excluded = Counter()
        for signal, relationship, video, channel in rows:
            if signal.status != "active" or signal.semantic_status != "current":
                excluded[f"{signal.status}/{signal.semantic_status}"] += 1
                continue
            effective.append(
                canonical(
                    {
                        **{k: getattr(signal, k) for k in SIGNAL_FIELDS},
                        "relationship_type": relationship,
                        "video_id": video,
                        "channel_id": channel,
                    }
                )
            )
        taxonomy = await RadarQueryRepository(session).taxonomy(
            "opportunity", [opportunity.id], "en-US"
        )
        context = {k: getattr(opportunity, k) for k in CONTEXT_FIELDS}
        context["taxonomy"] = {
            kind: taxonomy.get((opportunity.id, kind)) for kind in ("industry", "customer")
        }
        return canonical(
            {
                "signals": effective,
                "context": context,
                "excluded_counts": dict(sorted(excluded.items())),
                "source_diversity": {
                    "signal_count": len(effective),
                    "supporting_count": sum(
                        s["relationship_type"] == "supporting" for s in effective
                    ),
                    "video_count": len({s["video_id"] for s in effective if s["video_id"]}),
                    "channel_count": len({s["channel_id"] for s in effective if s["channel_id"]}),
                    "comment_count": sum(s["source_type"] == "comment" for s in effective),
                    "relationships": dict(Counter(s["relationship_type"] for s in effective)),
                    "signal_types": dict(Counter(s["signal_type"] for s in effective)),
                },
            }
        )

    async def _opportunity(self, session, identity, *, public=False, lock=False):
        query = select(Opportunity).where(Opportunity.id == identity)
        if lock:
            query = query.with_for_update()
        opportunity = await session.scalar(query)
        if opportunity is None or (public and opportunity.status != "active"):
            raise CandidateNotFound("Opportunity was not found")
        return opportunity

    @staticmethod
    def view(row):
        return canonical(
            {
                k: getattr(row, k)
                for k in (
                    "id",
                    "opportunity_id",
                    "version",
                    "status",
                    "source_evidence_hash",
                    "context_hash",
                    "input_hash",
                    "prompt_version",
                    "prompt_hash",
                    "provider",
                    "model",
                    "parsed_output",
                    "field_metadata",
                    "error_code",
                    "created_at",
                    "completed_at",
                    "review_status",
                    "reviewed_at",
                )
            }
        )

    async def current(self, identity, *, public=False):
        async with self.sessions() as session:
            opportunity = await self._opportunity(session, identity, public=public)
            bundle = await self.bundle(session, opportunity)
            rows = list(
                await session.scalars(
                    select(OpportunityConsolidation)
                    .where(OpportunityConsolidation.opportunity_id == identity)
                    .order_by(OpportunityConsolidation.version.desc())
                    .limit(100)
                )
            )
            prompt = resolve_prompt(FAMILY)

            def matching(r):
                return r.input_hash == digest(bundle) and r.prompt_hash == prompt.sha256

            completed = next((r for r in rows if r.status == "completed" and matching(r)), None)
            previous = completed or next((r for r in rows if r.status == "completed"), None)
            state = "current" if completed else "stale" if previous else "missing"
            if public:
                approved = next(
                    (
                        r
                        for r in rows
                        if r.status == "completed" and matching(r) and r.review_status == "approved"
                    ),
                    None,
                )
                # Explicit safe projection: no raw bundle, audit metadata or unreviewed proposals.
                return {
                    "state": "current" if approved else "unavailable",
                    "case": {
                        "id": str(approved.id),
                        "version": approved.version,
                        "parsed_output": {
                            **approved.parsed_output,
                            **{
                                k: {
                                    "text": None,
                                    "evidence_signal_ids": [],
                                    "information_class": "unknown",
                                    "support_level": "insufficient_evidence",
                                    "uncertainty": "Evidence insufficient",
                                }
                                for k in DIMENSIONS
                                if approved.parsed_output[k]["support_level"] == "hypothesis"
                            },
                        },
                        "field_metadata": approved.field_metadata,
                    }
                    if approved
                    else None,
                }
            return {
                "state": state,
                "case": self.view(previous) if previous else None,
                "latest_attempt": self.view(rows[0]) if rows else None,
                "source_diversity": bundle["source_diversity"],
                "excluded_counts": bundle["excluded_counts"],
                "opportunity_updated_at": opportunity.updated_at,
                "opportunity_status": opportunity.status,
                "history": [self.view(r) for r in rows],
                "history_has_more": len(rows) == 100,
            }

    async def request(self, identity, actor=None):
        prompt = resolve_prompt(FAMILY)
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            opportunity = await self._opportunity(session, identity, lock=True)
            if opportunity.status not in {"candidate", "active", "review"}:
                raise CandidateConflict("Opportunity is not eligible for consolidation")
            bundle = await self.bundle(session, opportunity)
            if (
                not bundle["signals"]
                or len(bundle["signals"]) > 200
                or len(json.dumps(bundle)) > 250000
            ):
                raise CandidateConflict(
                    "Consolidation requires 1–200 effective signals within the input limit"
                )
            rows = list(
                await session.scalars(
                    select(OpportunityConsolidation)
                    .where(OpportunityConsolidation.opportunity_id == identity)
                    .order_by(OpportunityConsolidation.version.desc())
                )
            )
            reusable = next(
                (
                    r
                    for r in rows
                    if r.status == "completed"
                    and r.input_hash == digest(bundle)
                    and r.prompt_hash == prompt.sha256
                ),
                None,
            )
            if reusable:
                return {"id": str(reusable.id), "status": "completed", "reused": True}
            pending = next((r for r in rows if r.status in {"queued", "running"}), None)
            if pending and (pending.started_at or pending.created_at) < now - timedelta(minutes=30):
                pending.status = "failed"
                pending.error_code = "lease_expired"
                pending.completed_at = now
                await session.flush()
                pending = None
            if pending:
                row = pending
            else:
                row = OpportunityConsolidation(
                    id=uuid4(),
                    opportunity_id=identity,
                    version=(rows[0].version + 1 if rows else 1),
                    status="queued",
                    source_evidence_hash=digest(bundle["signals"]),
                    context_hash=digest(bundle["context"]),
                    input_hash=digest(bundle),
                    prompt_version=prompt.version,
                    prompt_hash=prompt.sha256,
                    input_snapshot=bundle,
                    created_by=actor,
                    created_at=now,
                    review_status="pending",
                )
                session.add(row)
            result = {"id": str(row.id), "status": row.status, "reused": bool(pending)}
        if self.enqueuer and result["status"] == "queued":
            try:
                self.enqueuer.enqueue(
                    queue="opportunity_consolidation",
                    actor="consolidate_opportunity",
                    payload={"consolidation_id": result["id"]},
                )
            except Exception:
                # Redispatch the durable queued row through the same action/CLI.
                result["dispatch_failed"] = True
        return result

    async def execute(self, identity, ai, *, provider, model):
        async with self.sessions() as session, session.begin():
            row = await session.scalar(
                select(OpportunityConsolidation)
                .where(OpportunityConsolidation.id == identity)
                .with_for_update()
            )
            if row is None:
                raise CandidateNotFound("Consolidation was not found")
            if row.status != "queued":
                return {"id": str(row.id), "status": row.status, "reused": True}
            row.status, row.started_at = "running", datetime.now(UTC)
            row.provider, row.model = provider, model
            snapshot, version, prompt_hash = row.input_snapshot, row.prompt_version, row.prompt_hash
        response = None
        output = None
        metadata = None
        error_code = None
        failure_raw = None
        try:
            prompt = resolve_prompt(FAMILY, version)
            if prompt.sha256 != prompt_hash:
                raise ValueError("Immutable prompt hash mismatch")
            response = await asyncio.wait_for(
                ai.structured_generate(
                    task_type="opportunity_consolidation",
                    model=model,
                    system_prompt=prompt.content,
                    input_data=snapshot,
                    output_model=OpportunityConsolidationOutput,
                ),
                timeout=240,
            )
            output = OpportunityConsolidationOutput.model_validate(response.parsed)
            metadata = validate_grounding(output, snapshot)
            # Deterministic coverage gaps supplement (not replace) the model's editorial gaps.
            gaps = []
            gaps.extend(
                f"Evidence insufficient: {k}"
                for k in DIMENSIONS
                if getattr(output, k).support_level == "insufficient_evidence"
            )
            if snapshot["excluded_counts"]:
                gaps.append(
                    f"Excluded evidence: {snapshot['excluded_counts']}; not used as support."
                )
            gaps.append("Video/channel diversity is not independent customer validation.")
            output.validation_gaps = list(dict.fromkeys(gaps + output.validation_gaps))[:30]
        except Exception as error:
            error_code = (
                "invalid_output"
                if isinstance(error, (ValueError, AIStructuredOutputError))
                else "provider_failed"
            )
            failure_raw = getattr(error, "raw_output", None)
        async with self.sessions() as session, session.begin():
            row = await session.scalar(
                select(OpportunityConsolidation)
                .where(OpportunityConsolidation.id == identity)
                .with_for_update()
            )
            if row.status != "running":
                return {"id": str(identity), "status": row.status}
            row.status = "failed" if error_code else "completed"
            row.error_code, row.completed_at = error_code, datetime.now(UTC)
            if failure_raw:
                row.raw_output = failure_raw
            if response:
                row.raw_output = response.raw_output
                row.provider_request_id = response.provider_request_id
                row.input_tokens, row.output_tokens = response.input_tokens, response.output_tokens
            if not error_code:
                row.parsed_output = output.model_dump(mode="json")
                row.field_metadata = metadata
            return {"id": str(identity), "status": row.status, "error_code": error_code}

    async def _current_locked(self, session, opportunity, identity):
        row = await session.get(OpportunityConsolidation, identity)
        if row is None or row.opportunity_id != opportunity.id:
            raise CandidateNotFound("Consolidation was not found")
        if (
            row.status != "completed"
            or row.input_hash != digest(await self.bundle(session, opportunity))
            or row.prompt_hash != resolve_prompt(FAMILY).sha256
        ):
            raise CandidateConflict("Consolidation is missing, failed or stale; refresh first")
        return row

    async def approve(self, opportunity_id, identity, actor):
        async with self.sessions() as session, session.begin():
            opportunity = await self._opportunity(session, opportunity_id, lock=True)
            if opportunity.status not in {"candidate", "active", "review"}:
                raise CandidateConflict("Opportunity is no longer eligible")
            row = await self._current_locked(session, opportunity, identity)
            if row.review_status != "approved":
                row.review_status, row.reviewed_by, row.reviewed_at = (
                    "approved",
                    actor,
                    datetime.now(UTC),
                )
        return {"id": str(identity), "review_status": "approved"}

    async def accept(self, opportunity_id, identity, actor, request):
        field = PROPOSAL_FIELDS.get(request.dimension)
        if not field:
            raise CandidateConflict("This dimension has no supported canonical edit mapping")
        async with self.sessions() as session, session.begin():
            opportunity = await self._opportunity(session, opportunity_id, lock=True)
            if (
                opportunity.status != "candidate"
                or opportunity.updated_at != request.expected_updated_at
            ):
                raise CandidateConflict("Candidate changed; reload before accepting")
            row = await self._current_locked(session, opportunity, identity)
            proposal = row.parsed_output[request.dimension]
            if proposal["support_level"] not in {"supported", "partially_supported"}:
                raise CandidateConflict("Unsupported proposals cannot populate canonical fields")
            value = request.edited_text if request.edited_text is not None else proposal["text"]
            if not value or not value.strip() or (field == "business_model" and len(value) > 300):
                raise CandidateConflict("Invalid canonical field value")
            before = getattr(opportunity, field)
            if before != value:
                now = datetime.now(UTC)
                setattr(opportunity, field, value)
                opportunity.updated_at = now
                session.add(
                    OpportunityRevision(
                        opportunity_id=opportunity_id,
                        changed_by=actor,
                        changed_at=now,
                        field=field,
                        old_value=before,
                        new_value=value,
                        note=request.note,
                        source_consolidation_id=identity,
                    )
                )
        return {
            "field": field,
            "changed": before != value,
            "source_consolidation_id": str(identity),
        }
