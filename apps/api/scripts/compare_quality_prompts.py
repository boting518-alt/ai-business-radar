"""Run a bounded, read-only v001/v002 prompt comparison on local dental data."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import UUID

from ai_business_radar_schemas import (
    BusinessSignalExtractorOutput,
    IntelligenceTranslationOutput,
    OpportunityNormalizerOutput,
)

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import OpenAIClient, load_prompt
from ai_business_radar_api.infrastructure.ai.prompts import PROMPT_ROOT
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import Channel, Opportunity, Signal, Video
from ai_business_radar_api.services.opportunity_normalization import (
    OpportunityNormalizationService,
)
from ai_business_radar_api.services.signal_extraction import BusinessSignalExtractionService

VIDEO_ID = UUID("40ccdc96-0bae-4f44-b9cb-688cdb09d5c5")
NORMALIZER_SIGNAL_ID = UUID("3f5b6fcd-b047-4bf1-9785-678f9de34311")
OPPORTUNITY_ID = UUID("7eea70c0-eeee-4db5-9cd0-ca73dcd42861")
TRANSLATION_SIGNAL_IDS = (
    UUID("0a74cce1-79ee-47e1-b270-b7da6f6f5736"),
    UUID("3f5b6fcd-b047-4bf1-9785-678f9de34311"),
    UUID("4097d6ce-4c26-4e38-b190-c7da02030778"),
    UUID("63eda4a9-3176-45ad-8ecf-fecfcd7c954d"),
    UUID("6926dc73-ae72-4378-80df-c29a659dcd35"),
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def prompt_identity(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


async def generate(client, *, task, model, prompt, input_data, output_model):
    response = await client.structured_generate(
        task_type=task,
        model=model,
        system_prompt=prompt,
        input_data=input_data,
        output_model=output_model,
    )
    return {
        "provider": response.provider,
        "model": response.model,
        "prompt_hash": prompt_identity(prompt),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "output": response.parsed.model_dump(mode="json"),
    }


async def run(destination: Path) -> None:
    settings = Settings()
    database = settings.live_validation_database_url or settings.database_url
    required = (
        database,
        settings.openai_api_key,
        settings.ai_model_signal_extraction,
        settings.ai_model_opportunity_normalization,
        settings.intelligence_translation_model,
    )
    if settings.ai_provider != "openai" or any(value is None for value in required):
        raise RuntimeError("Configured database, OpenAI key, and all three models are required")

    engine = create_database_engine(database.get_secret_value())
    sessions = create_session_factory(engine)
    client = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    try:
        async with sessions() as session:
            video = await session.get(Video, VIDEO_ID)
            channel = await session.get(Channel, video.channel_id) if video else None
            signals = [await session.get(Signal, item) for item in TRANSLATION_SIGNAL_IDS]
            opportunity = await session.get(Opportunity, OPPORTUNITY_ID)
        incomplete = video is None or channel is None or opportunity is None
        if incomplete or any(x is None for x in signals):
            raise RuntimeError("The bounded dental validation dataset is incomplete")

        signal_input = BusinessSignalExtractionService._build_input(video, channel)
        normalizer = OpportunityNormalizationService(
            sessions,
            client,
            provider="openai",
            model=settings.ai_model_opportunity_normalization,
        )
        signal, source_context, candidates = await normalizer._load_context(
            NORMALIZER_SIGNAL_ID, force=True
        )
        normalizer_input = normalizer._build_input(signal, source_context, candidates)

        result = {
            "dataset": {
                "signal_extraction_video_id": str(VIDEO_ID),
                "normalizer_signal_id": str(NORMALIZER_SIGNAL_ID),
                "translation_signal_ids": [str(item) for item in TRANSLATION_SIGNAL_IDS],
                "translation_opportunity_id": str(OPPORTUNITY_ID),
            },
            "comparisons": {
                "signal_extractor": {},
                "opportunity_normalizer": {},
                "translation": {},
            },
        }
        for version in ("v001", "v002"):
            signal_prompt = load_prompt("signal-extractor", version)
            result["comparisons"]["signal_extractor"][version] = await generate(
                client,
                task="signal_extractor_quality_ab",
                model=settings.ai_model_signal_extraction,
                prompt=signal_prompt,
                input_data=signal_input,
                output_model=BusinessSignalExtractorOutput,
            )
            normalizer_prompt = load_prompt("opportunity-normalizer", version)
            result["comparisons"]["opportunity_normalizer"][version] = await generate(
                client,
                task="opportunity_normalizer_quality_ab",
                model=settings.ai_model_opportunity_normalization,
                prompt=normalizer_prompt,
                input_data=normalizer_input,
                output_model=OpportunityNormalizerOutput,
            )
            translation_prompt = (
                PROMPT_ROOT / "intelligence-translation" / "zh-CN" / f"{version}.md"
            ).read_text()
            translation_runs = []
            for translated_signal in signals:
                translation_runs.append(
                    await generate(
                        client,
                        task="intelligence_translation_quality_ab",
                        model=settings.intelligence_translation_model,
                        prompt=translation_prompt,
                        input_data={
                            "canonical_locale": "en-US",
                            "target_locale": "zh-CN",
                            "entity_type": "signal",
                            "fields": [
                                {
                                    "field_name": "statement",
                                    "source_text": translated_signal.statement,
                                }
                            ],
                        },
                        output_model=IntelligenceTranslationOutput,
                    )
                )
            translation_runs.append(
                await generate(
                    client,
                    task="intelligence_translation_quality_ab",
                    model=settings.intelligence_translation_model,
                    prompt=translation_prompt,
                    input_data={
                        "canonical_locale": "en-US",
                        "target_locale": "zh-CN",
                        "entity_type": "opportunity",
                        "fields": [
                            {"field_name": field, "source_text": getattr(opportunity, field)}
                            for field in ("name", "one_line_thesis", "problem", "solution")
                        ],
                    },
                    output_model=IntelligenceTranslationOutput,
                )
            )
            result["comparisons"]["translation"][version] = translation_runs

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(arguments().output))
