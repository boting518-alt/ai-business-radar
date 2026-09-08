"""Inspect or resume one legacy/partial Discovery Topic intelligence pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import (
    CollectionRun,
    DiscoveryTopicRun,
    Video,
    YouTubeDiscoveryItem,
)
from sqlalchemy import distinct, func, select

from ai_business_radar_workers.config import WorkerSettings
from ai_business_radar_workers.discovery_pipeline import resume_pipeline


async def inspect(topic_run_id: UUID, settings: WorkerSettings) -> dict:
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            batch = await session.get(DiscoveryTopicRun, topic_run_id)
            if batch is None:
                raise SystemExit(f"Topic run not found: {topic_run_id}")
            base = (
                select(YouTubeDiscoveryItem)
                .join(CollectionRun)
                .where(CollectionRun.topic_run_id == topic_run_id)
            )
            unique = await session.scalar(
                select(func.count(distinct(YouTubeDiscoveryItem.youtube_video_id)))
                .join(CollectionRun)
                .where(CollectionRun.topic_run_id == topic_run_id)
            )
            canonical = await session.scalar(
                select(func.count(distinct(YouTubeDiscoveryItem.canonical_video_id)))
                .join(CollectionRun)
                .where(
                    CollectionRun.topic_run_id == topic_run_id,
                    YouTubeDiscoveryItem.canonical_video_id.is_not(None),
                )
            )
            new = await session.scalar(
                select(func.count(distinct(YouTubeDiscoveryItem.youtube_video_id)))
                .join(CollectionRun)
                .outerjoin(Video, Video.youtube_video_id == YouTubeDiscoveryItem.youtube_video_id)
                .where(CollectionRun.topic_run_id == topic_run_id, Video.id.is_(None))
            )
            return {
                "topic_run_id": str(topic_run_id),
                "discovery_status": batch.status,
                "intelligence_status": batch.intelligence_status,
                "discovery_results": await session.scalar(
                    select(func.count()).select_from(base.subquery())
                ),
                "unique_videos": unique or 0,
                "new_videos": new or 0,
                "canonical_videos": canonical or 0,
                "next_stage": (
                    "none"
                    if batch.intelligence_status == "completed"
                    else "metadata_or_resume"
                ),
                "would_enqueue": batch.status not in {"queued", "running"}
                and batch.intelligence_status in {"not_started", "partial", "failed"},
            }
    finally:
        await engine.dispose()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-run-id", type=UUID, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 250:
        parser.error("--limit must be between 1 and 250")
    settings = WorkerSettings()
    report = await inspect(args.topic_run_id, settings)
    report["limit"] = args.limit
    if not args.dry_run and report["would_enqueue"]:
        report["enqueued"] = await resume_pipeline(
            args.topic_run_id, settings, batch_limit=args.limit
        )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
