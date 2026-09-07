"""Run bounded, artifact-only cross-source discovery and prompt validation."""

import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from ai_business_radar_schemas import (
    BusinessSignalExtractorOutput,
    IntelligenceTranslationOutput,
    OpportunityNormalizerOutput,
)
from pydantic import ValidationError

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import OpenAIClient, load_prompt
from ai_business_radar_api.infrastructure.ai.prompts import PROMPT_ROOT
from ai_business_radar_api.infrastructure.external.youtube import YouTubeAPIError, YouTubeClient

VERTICALS = {
    "dental_receptionist": {
        "query": "AI dental receptionist appointment booking",
        "candidate": "AI receptionist and appointment booking for dental practices",
        "customer": "dental practices",
        "problem": "missed calls and appointment handling",
        "solution": "AI receptionist and front-desk workflow automation",
    },
    "legal_intake": {
        "query": "AI legal intake assistant law firm receptionist",
        "candidate": "AI intake and lead qualification for law firms",
        "customer": "law firms",
        "problem": "unanswered inquiries and manual client intake",
        "solution": "AI receptionist, intake, and lead qualification workflow",
    },
    "property_management": {
        "query": "AI property management tenant inquiry automation",
        "candidate": "AI tenant inquiry and maintenance intake for property managers",
        "customer": "property managers",
        "problem": "repetitive tenant inquiries and maintenance request intake",
        "solution": "AI tenant support and request-routing automation",
    },
    "ecommerce_support": {
        "query": "AI ecommerce customer support agent Shopify",
        "candidate": "AI customer support and sales assistance for ecommerce stores",
        "customer": "ecommerce stores",
        "problem": "repetitive support questions and product-selection friction",
        "solution": "AI customer support and sales-assistance agent",
    },
    "bookkeeping": {
        "query": "AI bookkeeping automation small business accounting",
        "candidate": "AI bookkeeping workflow automation for small businesses",
        "customer": "small businesses and bookkeeping firms",
        "problem": "manual transaction categorization, reconciliation, and close workflows",
        "solution": "AI-assisted bookkeeping and accounting workflow automation",
    },
}
MAX_VIDEOS = 20
AB_VIDEOS = 10
MAX_NORMALIZER_CASES = 10
MAX_TRANSLATION_FIELDS = 16


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--normalizer-stress-only", action="store_true")
    parser.add_argument("--lexical-only", action="store_true")
    return parser.parse_args()


def prompt_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def generate(client, *, task, model, prompt, input_data, output_model):
    try:
        response = await client.structured_generate(
            task_type=task,
            model=model,
            system_prompt=prompt,
            input_data=input_data,
            output_model=output_model,
        )
    except ValidationError as error:
        return {
            "status": "invalid_output",
            "model": model,
            "prompt_hash": prompt_hash(prompt),
            "error_type": type(error).__name__,
        }
    return {
        "status": "completed",
        "provider": response.provider,
        "model": response.model,
        "prompt_hash": prompt_hash(prompt),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "output": response.parsed.model_dump(mode="json"),
    }


def signal_input(video, channel):
    return {
        "video": {
            "youtube_video_id": video.youtube_video_id,
            "title": video.title,
            "description": video.description,
            "published_at": video.published_at.isoformat(),
            "duration_seconds": video.duration_seconds,
            "language": video.language,
            "statistics": {
                "view_count": video.view_count,
                "like_count": video.like_count,
                "comment_count": video.comment_count,
            },
        },
        "channel": {"name": channel.name, "channel_type": None},
    }


def normalizer_input(vertical, video_id, video_title, published_at, extracted):
    definition = VERTICALS[vertical]
    signal_id = uuid5(NAMESPACE_URL, f"{vertical}:{video_id}")
    return {
        "signal": {
            "signal_id": str(signal_id),
            "signal_type": extracted.type.value,
            "statement": extracted.statement,
            "evidence_text": extracted.evidence,
            "industry": definition["customer"],
            "sub_industry": None,
            "customer_type": definition["customer"],
            "problem": definition["problem"],
            "solution": definition["solution"],
            "business_model": None,
            "technology": [],
            "claim_status": extracted.claim_status.value,
            "observed_at": published_at,
        },
        "source_context": {
            "source_type": "video",
            "youtube_video_id": video_id,
            "title": video_title,
            "published_at": published_at,
        },
        "candidates": [
            {
                "opportunity_id": str(uuid5(NAMESPACE_URL, f"ai-business-radar:{key}")),
                "name": value["candidate"],
                "one_line_thesis": None,
                "industry": value["customer"],
                "customer_type": value["customer"],
                "problem": value["problem"],
                "solution": value["solution"],
                "status": "candidate",
            }
            for key, value in VERTICALS.items()
        ],
    }


def lexical_candidate_review(result: dict) -> list[dict]:
    """Replay the production lexical ranking formula without database writes."""
    sources = {item["video_id"]: item for items in result["sources"].values() for item in items}
    reviews = []
    for case in result["signal_ab"][:MAX_NORMALIZER_CASES]:
        output = case["versions"]["v002"]
        if output["status"] != "completed" or not output["output"]["signals"]:
            continue
        extracted = BusinessSignalExtractorOutput.model_validate(output["output"]).signals[0]
        payload = normalizer_input(
            case["vertical"],
            case["video_id"],
            sources[case["video_id"]]["title"],
            None,
            extracted,
        )
        signal = payload["signal"]
        text = " ".join(
            str(signal.get(field) or "")
            for field in ("statement", "industry", "customer_type", "problem", "solution")
        ).lower()
        terms = sorted({word for word in re.findall(r"[\w-]{3,}", text) if not word.isdigit()})[:20]
        scored = []
        for candidate in payload["candidates"]:
            haystack = " ".join(
                str(candidate.get(field) or "").lower()
                for field in (
                    "name",
                    "one_line_thesis",
                    "industry",
                    "customer_type",
                    "problem",
                    "solution",
                )
            )
            scored.append(
                {
                    "opportunity_id": candidate["opportunity_id"],
                    "name": candidate["name"],
                    "score": sum(term in haystack for term in terms),
                }
            )
        scored.sort(key=lambda item: (-item["score"], item["name"].lower()))
        expected = str(uuid5(NAMESPACE_URL, f"ai-business-radar:{case['vertical']}"))
        reviews.append(
            {
                "vertical": case["vertical"],
                "video_id": case["video_id"],
                "signal_id": payload["signal"]["signal_id"],
                "terms": terms,
                "expected_opportunity_id": expected,
                "expected_rank": next(
                    index
                    for index, candidate in enumerate(scored, start=1)
                    if candidate["opportunity_id"] == expected
                ),
                "ranked_candidates": scored,
            }
        )
    return reviews


async def run(
    destination: Path,
    *,
    normalizer_stress_only: bool = False,
    lexical_only: bool = False,
):
    if lexical_only:
        result = json.loads(destination.read_text())
        result["lexical_candidate_review"] = lexical_candidate_review(result)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return
    settings = Settings()
    required = (
        settings.youtube_api_key,
        settings.openai_api_key,
        settings.ai_model_signal_extraction,
        settings.ai_model_opportunity_normalization,
        settings.intelligence_translation_model,
    )
    if settings.ai_provider != "openai" or any(value is None for value in required):
        raise RuntimeError("YouTube/OpenAI credentials and validation models are required")

    youtube = YouTubeClient(
        settings.youtube_api_key.get_secret_value(),
        timeout_seconds=settings.youtube_http_timeout_seconds,
        max_retries=settings.youtube_max_retries,
    )
    ai = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    if normalizer_stress_only:
        result = json.loads(destination.read_text())
        result["normalizer_ab"] = []
        sources = {item["video_id"]: item for items in result["sources"].values() for item in items}
        for case in result["signal_ab"][:MAX_NORMALIZER_CASES]:
            v002 = case["versions"]["v002"]
            if v002["status"] != "completed" or not v002["output"]["signals"]:
                continue
            source = sources[case["video_id"]]
            extracted = BusinessSignalExtractorOutput.model_validate(v002["output"]).signals[0]
            payload = normalizer_input(
                case["vertical"], case["video_id"], source["title"], None, extracted
            )
            item = {
                "vertical": case["vertical"],
                "video_id": case["video_id"],
                "expected_opportunity_id": str(
                    uuid5(NAMESPACE_URL, f"ai-business-radar:{case['vertical']}")
                ),
                "candidate_count": len(payload["candidates"]),
                "versions": {},
            }
            for version in ("v001", "v002"):
                prompt = load_prompt("opportunity-normalizer", version)
                item["versions"][version] = await generate(
                    ai,
                    task="cross_source_normalizer_stress_ab",
                    model=settings.ai_model_opportunity_normalization,
                    prompt=prompt,
                    input_data=payload,
                    output_model=OpportunityNormalizerOutput,
                )
            result["normalizer_ab"].append(item)
            destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        await youtube.aclose()
        return
    result = {
        "limits": {
            "videos": MAX_VIDEOS,
            "search_requests": len(VERTICALS),
            "ab_source_inputs": AB_VIDEOS,
            "normalizer_cases": MAX_NORMALIZER_CASES,
            "translation_fields": MAX_TRANSLATION_FIELDS,
            "provider_calls_planned": 48,
            "provider_calls_failure_allowance": 20,
        },
        "youtube_quota_estimate": 0,
        "queries": {},
        "sources": {},
        "signal_ab": [],
        "normalizer_ab": [],
        "translation_ab": [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    try:
        selected = []
        for vertical, definition in VERTICALS.items():
            page = await youtube.search_videos(definition["query"], max_results=12)
            result["youtube_quota_estimate"] += 100
            unique_channels = set()
            search_items = []
            for item in page.items:
                if item.youtube_channel_id in unique_channels:
                    continue
                unique_channels.add(item.youtube_channel_id)
                search_items.append(item)
                if len(search_items) == 4:
                    break
            result["queries"][vertical] = definition["query"]
            videos = await youtube.get_videos([item.youtube_video_id for item in search_items])
            channel_ids = [item.youtube_channel_id for item in search_items]
            channels = await youtube.get_channels(channel_ids)
            result["youtube_quota_estimate"] += 2
            by_channel = {item.youtube_channel_id: item for item in channels}
            result["sources"][vertical] = []
            for video in videos:
                channel = by_channel[video.youtube_channel_id]
                comment_count = 0
                try:
                    result["youtube_quota_estimate"] += 1
                    comments = await youtube.get_comment_threads(
                        video.youtube_video_id, max_results=3
                    )
                    comment_count = len(comments.items)
                except YouTubeAPIError:
                    pass
                record = {
                    "video_id": video.youtube_video_id,
                    "title": video.title,
                    "channel_id": channel.youtube_channel_id,
                    "channel": channel.name,
                    "comments_sampled": comment_count,
                }
                result["sources"][vertical].append(record)
                selected.append((vertical, video, channel))
            checkpoint()

        ab_selected = []
        for vertical in VERTICALS:
            ab_selected.extend([item for item in selected if item[0] == vertical][:2])
        signal_outputs = {}
        for vertical, video, channel in ab_selected[:AB_VIDEOS]:
            item = {"vertical": vertical, "video_id": video.youtube_video_id, "versions": {}}
            for version in ("v001", "v002"):
                prompt = load_prompt("signal-extractor", version)
                item["versions"][version] = await generate(
                    ai,
                    task="cross_source_signal_ab",
                    model=settings.ai_model_signal_extraction,
                    prompt=prompt,
                    input_data=signal_input(video, channel),
                    output_model=BusinessSignalExtractorOutput,
                )
            result["signal_ab"].append(item)
            v002 = item["versions"]["v002"]
            if v002["status"] == "completed":
                signal_outputs[(vertical, video.youtube_video_id)] = v002["output"]
            checkpoint()

        for vertical, video, _channel in ab_selected[:MAX_NORMALIZER_CASES]:
            extracted = signal_outputs.get((vertical, video.youtube_video_id))
            if extracted is None:
                continue
            output = BusinessSignalExtractorOutput.model_validate(extracted)
            if not output.signals:
                continue
            payload = normalizer_input(
                vertical,
                video.youtube_video_id,
                video.title,
                video.published_at.isoformat(),
                output.signals[0],
            )
            item = {
                "vertical": vertical,
                "video_id": video.youtube_video_id,
                "expected_opportunity_id": payload["candidates"][0]["opportunity_id"],
                "versions": {},
            }
            for version in ("v001", "v002"):
                prompt = load_prompt("opportunity-normalizer", version)
                item["versions"][version] = await generate(
                    ai,
                    task="cross_source_normalizer_ab",
                    model=settings.ai_model_opportunity_normalization,
                    prompt=prompt,
                    input_data=payload,
                    output_model=OpportunityNormalizerOutput,
                )
            result["normalizer_ab"].append(item)
            checkpoint()

        translation_fields = []
        for vertical in list(VERTICALS)[1:]:
            vertical_statements = []
            for item in result["signal_ab"]:
                if item["vertical"] != vertical:
                    continue
                v002 = item["versions"]["v002"]
                if v002["status"] == "completed":
                    vertical_statements.extend(v002["output"]["signals"])
            for statement in vertical_statements[:4]:
                translation_fields.append((vertical, statement["statement"]))
        translation_fields = translation_fields[:MAX_TRANSLATION_FIELDS]
        for offset in range(0, len(translation_fields), 4):
            group = translation_fields[offset : offset + 4]
            item = {"verticals": [value[0] for value in group], "versions": {}}
            payload = {
                "canonical_locale": "en-US",
                "target_locale": "zh-CN",
                "entity_type": "quality_case",
                "fields": [
                    {"field_name": f"statement_{index}", "source_text": value[1]}
                    for index, value in enumerate(group, start=1)
                ],
            }
            for version in ("v001", "v002"):
                prompt = (
                    PROMPT_ROOT / "intelligence-translation" / "zh-CN" / f"{version}.md"
                ).read_text()
                item["versions"][version] = await generate(
                    ai,
                    task="cross_source_translation_ab",
                    model=settings.intelligence_translation_model,
                    prompt=prompt,
                    input_data=payload,
                    output_model=IntelligenceTranslationOutput,
                )
            result["translation_ab"].append(item)
            checkpoint()

        checkpoint()
    finally:
        await youtube.aclose()


if __name__ == "__main__":
    options = arguments()
    asyncio.run(
        run(
            options.output,
            normalizer_stress_only=options.normalizer_stress_only,
            lexical_only=options.lexical_only,
        )
    )
