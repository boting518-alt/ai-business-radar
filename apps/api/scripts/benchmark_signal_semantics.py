"""Artifact-only v003/v004 comparison on four persisted metadata inputs (8 model calls)."""

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from ai_business_radar_schemas import BusinessSignalExtractorOutput

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import OpenAIClient, resolve_prompt
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import Channel, Video
from ai_business_radar_api.services.signal_extraction import BusinessSignalExtractionService
from ai_business_radar_api.services.signal_semantics import evaluate

ROOT = Path(__file__).parents[3]
VIDEO_IDS = [
    "5d17d344-67de-49e6-a528-b63d663d5a11",
    "39ca1527-825e-4f67-87ad-03301980cfa2",
    "4aa31507-bf00-4c9a-870f-0a4ac17a735d",
    "10821271-c3f6-4725-9259-a39b1c9ddcb2",
]


def regression():
    corpus = json.loads((ROOT / "tests/fixtures/signal_semantics/real-cases.json").read_text())
    results = []
    for case in corpus["cases"]:
        result = evaluate(case["signal_type"], case["statement"], case["evidence_text"])
        results.append(
            dict(
                signal_id=case["id"],
                signal_type=case["signal_type"],
                gold=case["gold"],
                predicted=asdict(result),
            )
        )

    def fraction(items, predicate):
        return dict(numerator=sum(predicate(x) for x in items), denominator=len(items))

    accepted_pi = [
        x
        for x in results
        if x["signal_type"] == "purchase_intent" and x["predicted"]["decision"] == "accept"
    ]
    cta = [x for x in results if x["gold"]["evidence_role"] == "seller_cta"]
    money = [x for x in results if x["gold"]["evidence_role"] == "creator_monetization"]
    revenue = [x for x in results if x["signal_type"] == "revenue"]
    return dict(
        method=corpus["method"],
        cases=results,
        metrics={
            "purchase_intent_precision": fraction(
                accepted_pi, lambda x: x["gold"]["valid_category"]
            ),
            "revenue_ownership_accuracy": fraction(
                revenue,
                lambda x: (x["predicted"]["decision"] == "accept") == x["gold"]["valid_category"],
            ),
            "actor_role_accuracy": fraction(
                results, lambda x: x["predicted"]["actor_role"] == x["gold"]["actor_role"]
            ),
            "evidence_role_accuracy": fraction(
                results, lambda x: x["predicted"]["evidence_role"] == x["gold"]["evidence_role"]
            ),
            "false_positive_cta_rate": fraction(
                cta, lambda x: x["predicted"]["decision"] == "accept"
            ),
            "creator_product_monetization_confusion": fraction(
                money,
                lambda x: x["predicted"]["decision"] == "accept" and x["signal_type"] == "revenue",
            ),
            "decision_agreement": fraction(
                results, lambda x: x["predicted"]["decision"] == x["gold"]["decision"]
            ),
        },
    )


async def run(destination, live):
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "guardrail-benchmark.json").write_text(
        json.dumps(regression(), ensure_ascii=False, indent=2) + "\n"
    )
    if not live:
        return
    settings = Settings()
    engine = create_database_engine(settings.database_url.get_secret_value())
    client = OpenAIClient(settings.openai_api_key.get_secret_value(), max_retries=0)
    try:
        async with create_session_factory(engine)() as session:
            inputs = []
            for identity in VIDEO_IDS:
                video = await session.get(Video, UUID(identity))
                channel = await session.get(Channel, video.channel_id)
                inputs.append(BusinessSignalExtractionService._build_input(video, channel))
        for index, input_data in enumerate(inputs):
            digest = hashlib.sha256(json.dumps(input_data, sort_keys=True).encode()).hexdigest()
            for version in ("v003", "v004"):
                path = destination / f"prompt-{index}-{version}.json"
                if path.exists():
                    continue
                prompt = resolve_prompt("signal-extractor", version)
                record = dict(
                    prompt_version=version,
                    prompt_hash=prompt.sha256,
                    input_hash=digest,
                    input=input_data,
                    model=settings.ai_model_signal_extraction,
                )
                try:
                    response = await client.structured_generate(
                        task_type="signal_semantic_benchmark",
                        model=settings.ai_model_signal_extraction,
                        system_prompt=prompt.content,
                        input_data=input_data,
                        output_model=BusinessSignalExtractorOutput,
                    )
                    parsed = BusinessSignalExtractorOutput.model_validate(response.parsed)
                    record.update(
                        status="completed",
                        provider=response.provider,
                        raw_output=response.raw_output,
                        parsed_output=parsed.model_dump(mode="json"),
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        provider_request_id=response.provider_request_id,
                    )
                except Exception as error:
                    record.update(status="failed", error_type=type(error).__name__)
                path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n"
                )
                print(index, version, record["status"], flush=True)
    finally:
        await engine.dispose()
        await client.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.live))
