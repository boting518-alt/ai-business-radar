#!/usr/bin/env python3
"""Run one bounded automatic-translation coverage reconciliation."""

import argparse
import asyncio
import json

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.queue import JobEnqueuer
from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverageReconciliationService,
    TranslationReconciliationRequest,
)


async def run(locale: str, limit: int, dry_run: bool, use_live_validation_db: bool) -> dict:
    settings = Settings()
    selected_database_url = (
        settings.live_validation_database_url if use_live_validation_db else settings.database_url
    )
    if selected_database_url is None:
        variable = "LIVE_VALIDATION_DATABASE_URL" if use_live_validation_db else "DATABASE_URL"
        raise RuntimeError(f"{variable} is not configured")
    if not dry_run and settings.redis_url is None:
        raise RuntimeError("REDIS_URL is not configured")
    engine = create_database_engine(selected_database_url.get_secret_value())
    try:
        service = TranslationCoverageReconciliationService(
            create_session_factory(engine),
            None
            if dry_run
            else JobEnqueuer(settings.redis_url.get_secret_value()),  # type: ignore[union-attr]
        )
        result = await service.reconcile(
            TranslationReconciliationRequest(locale=locale, limit=limit, dry_run=dry_run)
        )
        return result.model_dump(mode="json")
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="zh-CN", choices=("zh-CN",))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-live-validation-db", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                asyncio.run(
                    run(args.locale, args.limit, args.dry_run, args.use_live_validation_db)
                ),
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
