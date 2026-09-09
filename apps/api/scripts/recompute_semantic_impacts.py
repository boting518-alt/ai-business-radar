"""Append corrected trend/score history for exactly the opportunities in an applied audit report."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.opportunity_scoring import OpportunityScoringService
from ai_business_radar_api.services.trend_aggregation import (
    OpportunityTrendAggregationService,
    TrendAggregationRequest,
)


async def main(args):
    report = json.loads(args.audit_report.read_text())
    ids = [UUID(value) for value in report["score_impact_candidates"]]
    if not report.get("applied") or len(ids) > 100:
        raise ValueError("An applied bounded audit report is required")
    end = datetime.fromisoformat(report["generated_at"])
    if end.utcoffset() is None:
        raise ValueError("Audit time must be timezone-aware")
    if not args.apply:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "opportunities": list(map(str, ids)),
                    "period_end": end.isoformat(),
                }
            )
        )
        return
    engine = create_database_engine(Settings().database_url.get_secret_value())
    factory = create_session_factory(engine)
    trends = OpportunityTrendAggregationService(factory)
    scores = OpportunityScoringService(factory, clock=lambda: end)
    results = []
    try:
        for identity in ids:
            snapshots = []
            for window in ("7d", "30d", "90d"):
                snapshot = await trends.aggregate(
                    TrendAggregationRequest(
                        opportunity_id=identity, window_type=window, period_end=end
                    )
                )
                snapshots.append(snapshot.model_dump(mode="json"))
            score = await scores.score(identity, force=True)
            results.append(
                {
                    "opportunity_id": str(identity),
                    "trends": snapshots,
                    "score": score.model_dump(mode="json"),
                }
            )
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
        print(f"Appended/reused corrected history for {len(results)} opportunities")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args))
