"""Bounded local runner for persisted intelligence translations."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import AIConfigurationError, OpenAIClient
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.services.intelligence_translation import (
    IntelligenceTranslationService,
    TranslationBatchRequest,
    TranslationRequest,
)


class DryRunAI:
    async def structured_generate(self, **_kwargs):
        raise AssertionError("dry-run must not call AI")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Translate canonical intelligence into zh-CN")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("signal", "opportunity"):
        command = commands.add_parser(name)
        command.add_argument("--id", type=UUID, required=True)
        command.add_argument("--locale", default="zh-CN", choices=["zh-CN"])
        command.add_argument("--fields", nargs="+")
        add_common(command)
    batch = commands.add_parser("batch")
    batch.add_argument("--entity-type", choices=["signals", "opportunities", "all"], default="all")
    batch.add_argument("--locale", default="zh-CN", choices=["zh-CN"])
    batch.add_argument("--limit", type=int, default=20, choices=range(1, 51), metavar="1..50")
    batch.add_argument("--only-stale", action="store_true")
    batch.add_argument("--include-stale", action="store_true")
    add_common(batch)
    return root


def add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--force", action="store_true")
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--show-sample", action="store_true")
    command.add_argument("--artifact-dir", type=Path)


async def run(args: argparse.Namespace) -> int:
    settings = Settings()
    database = settings.live_validation_database_url or settings.database_url
    if database is None:
        raise AIConfigurationError("LIVE_VALIDATION_DATABASE_URL or DATABASE_URL is required")
    if not args.dry_run and (
        settings.ai_provider != "openai"
        or settings.openai_api_key is None
        or not settings.intelligence_translation_model
    ):
        raise AIConfigurationError(
            "AI_PROVIDER=openai, OPENAI_API_KEY and INTELLIGENCE_TRANSLATION_MODEL are required"
        )
    engine = create_database_engine(database.get_secret_value())
    client = (
        DryRunAI()
        if args.dry_run
        else OpenAIClient(
            settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
        )
    )
    service = IntelligenceTranslationService(
        create_session_factory(engine),
        client,
        provider=settings.ai_provider or "openai",
        model=settings.intelligence_translation_model or "dry-run",
    )
    try:
        if args.command == "batch":
            result = await service.translate_batch(
                TranslationBatchRequest(
                    entity_type=args.entity_type,
                    locale=args.locale,
                    limit=args.limit,
                    force=args.force,
                    only_missing=not args.only_stale and not args.include_stale,
                    only_stale=args.only_stale,
                    dry_run=args.dry_run,
                )
            )
        else:
            result = await service.translate_entity(
                TranslationRequest(
                    entity_type=args.command,
                    entity_id=args.id,
                    locale=args.locale,
                    force=args.force,
                    fields=args.fields,
                    dry_run=args.dry_run,
                )
            )
    finally:
        await engine.dispose()
    payload = result.model_dump(mode="json")
    if not args.show_sample:
        for item in payload.get("results", [payload]):
            item.pop("plan", None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.artifact_dir:
        write_artifact(args.artifact_dir, payload)
    return 0


def write_artifact(root: Path, payload: dict) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = root / stamp
    destination.mkdir(parents=True, exist_ok=False)
    items = payload.get("results", [payload])
    lines = [
        "# Intelligence Translation Validation",
        "",
        "Local validation data; not production intelligence.",
        "",
        f"- Generated: {stamp}",
        f"- Processed: {len(items)}",
    ]
    for item in items:
        lines.extend(
            [
                "",
                f"## {item['entity_type']} `{item['entity_id']}`",
                "",
                f"- Translated: {', '.join(item['translated_fields']) or 'none'}",
                f"- Reused: {', '.join(item['reused_fields']) or 'none'}",
                f"- Provider/model: {item['provider']} / {item['model']}",
                f"- Version: {item['translation_version']}",
                f"- Tokens: input={item.get('input_tokens')}, output={item.get('output_tokens')}",
            ]
        )
    path = destination / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))
