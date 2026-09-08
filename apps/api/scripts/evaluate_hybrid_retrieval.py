"""Evaluate offline hybrid retrieval and v003 prompts without persistence."""

import argparse
import asyncio
import json
import math
from pathlib import Path

from ai_business_radar_schemas import (
    BusinessSignalExtractorOutput,
    IntelligenceTranslationOutput,
    OpportunityNormalizerOutput,
)
from openai import AsyncOpenAI
from validate_semantic_separation import (
    CANDIDATES,
    candidate,
    generate,
    normalizer_payload,
    retrieve,
    signal_payload,
)

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import OpenAIClient, load_prompt
from ai_business_radar_api.infrastructure.ai.prompts import PROMPT_ROOT
from ai_business_radar_api.infrastructure.external.youtube import YouTubeClient

EMBEDDING_MODEL = "text-embedding-3-small"
LEXICAL_K = 5
SEMANTIC_K = 5
UNION_LIMIT = 10
WEIGHTS = ((0.7, 0.3), (0.5, 0.5), (0.3, 0.7))


def args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def semantic_text(item: dict) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("name", "customer_type", "problem", "solution", "industry")
    )


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if high == low:
        return {key: 1.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def rank_case(
    case: dict,
    candidate_vectors: dict[str, list[float]],
    query_vector: list[float],
) -> dict:
    lexical = retrieve(case["input_text"])
    lexical_scores = {item["candidate_id"]: float(item["score"]) for item in lexical}
    semantic_scores = {key: cosine(query_vector, candidate_vectors[key]) for key in CANDIDATES}
    semantic = sorted(semantic_scores, key=lambda key: (-semantic_scores[key], key))
    lexical_ids = [item["candidate_id"] for item in lexical[:LEXICAL_K]]
    semantic_ids = semantic[:SEMANTIC_K]
    union_ids = list(dict.fromkeys([*lexical_ids, *semantic_ids]))[:UNION_LIMIT]
    lexical_normalized = normalize({key: lexical_scores.get(key, 0.0) for key in CANDIDATES})
    semantic_normalized = normalize(semantic_scores)
    reranks = {}
    for alpha, beta in WEIGHTS:
        name = f"lexical_{alpha:.1f}_semantic_{beta:.1f}"
        reranks[name] = sorted(
            union_ids,
            key=lambda key: (
                -(alpha * lexical_normalized.get(key, 0.0) + beta * semantic_normalized[key]),
                key,
            ),
        )
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "input_text": case["input_text"],
        "source_title": case.get("source_title"),
        "expected_candidate": case["expected_candidate"],
        "expected_opportunity_id": case["expected_opportunity_id"],
        "lexical": lexical_ids,
        "semantic": semantic_ids,
        "union": union_ids,
        "weighted": reranks,
        "semantic_scores": {key: round(semantic_scores[key], 6) for key in semantic_ids},
    }


def metrics(cases: list[dict], strategy: str, *, low_overlap: bool = False) -> dict:
    selected = [
        case
        for case in cases
        if not low_overlap or case["family"] == "carefully_selected_low_overlap"
    ]
    ranks = []
    sizes = []
    for case in selected:
        values = case[strategy] if strategy != "weighted_best" else case["weighted_best"]
        sizes.append(len(values))
        ranks.append(
            next(
                (index for index, key in enumerate(values, 1) if key == case["expected_candidate"]),
                None,
            )
        )
    return {
        "cases": len(selected),
        "recall_at_1": sum(rank == 1 for rank in ranks) / len(ranks),
        "recall_at_3": sum(rank is not None and rank <= 3 for rank in ranks) / len(ranks),
        "recall_at_5": sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks),
        "mrr": sum(1 / rank for rank in ranks if rank) / len(ranks),
        "mean_candidate_set_size": sum(sizes) / len(sizes),
        "irrelevant_candidate_rate": sum(
            len(values) - int(rank is not None)
            for values, rank in zip(
                (
                    case[strategy] if strategy != "weighted_best" else case["weighted_best"]
                    for case in selected
                ),
                ranks,
                strict=True,
            )
        )
        / sum(sizes),
    }


def bounded_candidates(keys: list[str]) -> list[dict]:
    return [candidate(key) for key in keys[:UNION_LIMIT]]


async def run(baseline_path: Path, destination: Path):
    baseline = json.loads(baseline_path.read_text())
    settings = Settings()
    embedding_client = AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    ai = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    source_cases = baseline["retrieval_normalizer_ab"]
    candidate_keys = list(CANDIDATES)
    texts = [semantic_text(candidate(key)) for key in candidate_keys]
    texts.extend(case["input_text"] for case in source_cases)
    response = await embedding_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    candidate_vectors = dict(zip(candidate_keys, vectors[: len(candidate_keys)], strict=True))
    query_vectors = vectors[len(candidate_keys) :]
    cases = [
        rank_case(case, candidate_vectors, vector)
        for case, vector in zip(source_cases, query_vectors, strict=True)
    ]

    weight_metrics = {}
    for alpha, beta in WEIGHTS:
        name = f"lexical_{alpha:.1f}_semantic_{beta:.1f}"
        for case in cases:
            case[name] = case["weighted"][name]
        weight_metrics[name] = metrics(cases, name)
    best = max(
        weight_metrics,
        key=lambda name: (
            weight_metrics[name]["recall_at_5"],
            weight_metrics[name]["mrr"],
        ),
    )
    for case in cases:
        case["weighted_best"] = case["weighted"][best]

    result = {
        "baseline_artifact": str(baseline_path),
        "embedding": {
            "model": EMBEDDING_MODEL,
            "request_count": 1,
            "input_count": len(texts),
            "tokens": response.usage.total_tokens,
        },
        "limits": {
            "lexical_k": LEXICAL_K,
            "semantic_k": SEMANTIC_K,
            "union_limit": UNION_LIMIT,
        },
        "best_weighted_strategy": best,
        "metrics": {
            "lexical": metrics(cases, "lexical"),
            "semantic": metrics(cases, "semantic"),
            "union": metrics(cases, "union"),
            "weighted": weight_metrics,
            "weighted_best": metrics(cases, "weighted_best"),
            "low_overlap": {
                name: metrics(cases, name, low_overlap=True)
                for name in ("lexical", "semantic", "union", "weighted_best")
            },
        },
        "cases": cases,
        "normalizer_hybrid_ab": [],
        "signal_v003_ab": [],
        "translation_v003_ab": [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    checkpoint()
    for source, ranked in zip(source_cases, cases, strict=True):
        keys = ranked["weighted_best"]
        payload = normalizer_payload(
            source["case_id"],
            source["input_text"],
            source["expected_candidate"],
            [{"candidate_id": key, "score": 0, **candidate(key)} for key in keys],
            source.get("source_title") or "Validation source",
        )
        item = {
            "case_id": source["case_id"],
            "expected_opportunity_id": source["expected_opportunity_id"],
            "candidate_ids": [item["opportunity_id"] for item in payload["candidates"]],
            "versions": {},
        }
        for version in ("v001", "v002"):
            item["versions"][version] = await generate(
                ai,
                task="hybrid_normalizer_ab",
                model=settings.ai_model_opportunity_normalization,
                prompt=load_prompt("opportunity-normalizer", version),
                payload={
                    key: value for key, value in payload.items() if key != "expected_opportunity_id"
                },
                output_model=OpportunityNormalizerOutput,
            )
        result["normalizer_hybrid_ab"].append(item)
        checkpoint()

    youtube = YouTubeClient(settings.youtube_api_key.get_secret_value())
    try:
        video_ids = [case["video_id"] for case in baseline["signal_ab"]]
        videos = await youtube.get_videos(video_ids)
        channel_ids = list(dict.fromkeys(video.youtube_channel_id for video in videos))
        channels = await youtube.get_channels(channel_ids)
        channel_map = {channel.youtube_channel_id: channel for channel in channels}
        for video in videos:
            payload = signal_payload(video, channel_map[video.youtube_channel_id])
            item = {"video_id": video.youtube_video_id, "versions": {}}
            for version in ("v002", "v003"):
                item["versions"][version] = await generate(
                    ai,
                    task="signal_v003_ab",
                    model=settings.ai_model_signal_extraction,
                    prompt=load_prompt("signal-extractor", version),
                    payload=payload,
                    output_model=BusinessSignalExtractorOutput,
                )
            result["signal_v003_ab"].append(item)
            checkpoint()
    finally:
        await youtube.aclose()

    fields = [field for group in baseline["translation_ab"] for field in group["source_fields"]]
    for offset in range(0, len(fields), 4):
        selected = fields[offset : offset + 4]
        payload = {
            "canonical_locale": "en-US",
            "target_locale": "zh-CN",
            "entity_type": "prompt_fix_validation",
            "fields": [
                {"field_name": f"field_{offset + index}", "source_text": text}
                for index, text in enumerate(selected, 1)
            ],
        }
        item = {"source_fields": selected, "versions": {}}
        for version in ("v002", "v003"):
            prompt = (
                PROMPT_ROOT / "intelligence-translation" / "zh-CN" / f"{version}.md"
            ).read_text()
            item["versions"][version] = await generate(
                ai,
                task="translation_v003_ab",
                model=settings.intelligence_translation_model,
                prompt=prompt,
                payload=payload,
                output_model=IntelligenceTranslationOutput,
            )
        result["translation_v003_ab"].append(item)
        checkpoint()


if __name__ == "__main__":
    options = args()
    asyncio.run(run(options.baseline, options.output))
