"""Bounded dry-run/reconciliation. No paid work without explicit --enqueue."""

import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import Opportunity
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.opportunity_consolidation import OpportunityConsolidationService


async def main(args):
    settings = Settings()
    engine = create_database_engine(settings.database_url.get_secret_value())
    sessions = create_session_factory(engine)
    if args.enqueue and not settings.redis_url:
        raise ValueError("Redis is required for enqueue")
    queue = JobEnqueuer(settings.redis_url.get_secret_value()) if args.enqueue else None
    service = OpportunityConsolidationService(sessions, queue)
    try:
        async with sessions() as session:
            query = (
                select(Opportunity.id)
                .where(Opportunity.status == args.status)
                .order_by(Opportunity.id)
                .limit(args.limit)
            )
            if args.opportunity_id:
                query = select(Opportunity.id).where(Opportunity.id == UUID(args.opportunity_id))
            ids = list(await session.scalars(query))
        results = []
        for identity in ids:
            state = await service.current(identity)
            eligible = 0 < state["source_diversity"]["signal_count"] <= 200 and state[
                "opportunity_status"
            ] in {"active", "candidate", "review"}
            item = {
                "id": str(identity),
                "state": state["state"],
                "eligible": eligible,
                "would_enqueue": eligible and state["state"] != "current",
            }
            if args.enqueue and item["would_enqueue"]:
                item["result"] = await service.request(identity)
            results.append(item)
        print(
            json.dumps(
                {
                    "dry_run": not args.enqueue,
                    "selected": len(ids),
                    "eligible": sum(r["eligible"] for r in results),
                    **{
                        k: sum(r["state"] == k for r in results)
                        for k in ("current", "stale", "missing")
                    },
                    "would_enqueue": sum(r["would_enqueue"] for r in results),
                    "items": results,
                },
                indent=2,
            )
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=["candidate", "active", "review"], default="candidate")
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--opportunity-id")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--enqueue", action="store_true")
    asyncio.run(main(parser.parse_args()))
