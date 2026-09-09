"""Bounded local semantic audit. Default is read-only; --apply is intentional mutation."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.signal_semantic_audit import audit


async def main(args):
    settings = Settings()
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        report = await audit(create_session_factory(engine), limit=args.limit, apply=args.apply)
        report["generated_at"] = datetime.now(UTC).isoformat()
        output = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output + "\n")
        print(output)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=["active"], default="active")
    parser.add_argument("--limit", type=int, default=100)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("limit must be between 1 and 100")
    asyncio.run(main(args))
