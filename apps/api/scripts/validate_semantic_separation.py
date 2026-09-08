"""Run bounded, artifact-only semantic separation validation."""

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
from ai_business_radar_api.infrastructure.external.youtube import YouTubeClient

SEARCH_CASES = [
    ("dental_insurance", "AI dental insurance verification automation"),
    ("dental_recall", "AI dental patient recall reactivation automation"),
    ("legal_drafting", "AI legal document drafting law firm"),
    ("legal_billing", "AI legal billing collections automation"),
    ("property_maintenance", "AI property maintenance triage vendor dispatch"),
    ("property_leasing", "AI property leasing lead qualification"),
    ("ecommerce_cart", "AI abandoned cart recovery Shopify agent"),
    ("ecommerce_reviews", "AI ecommerce review generation automation"),
    ("bookkeeping_invoice", "AI invoice data extraction bookkeeping"),
    ("bookkeeping_cashflow", "AI cash flow advisor small business accounting"),
    ("veterinary_reception", "AI veterinary receptionist appointment booking"),
    ("hvac_reception", "AI HVAC receptionist quote booking"),
    ("multilingual_ja_dental", "歯科 AI 受付"),
    ("multilingual_zh_legal", "AI 律所接待"),
]

CANDIDATES = {
    "dental_reception": (
        "AI receptionist for dental practices",
        "dental practices",
        "missed calls and appointment booking",
        "automated front desk",
    ),
    "dental_insurance": (
        "Dental insurance verification automation",
        "dental practices",
        "manual insurance eligibility checks",
        "automated benefits verification",
    ),
    "dental_recall": (
        "Dental patient recall and reactivation automation",
        "dental practices",
        "overdue patient recall",
        "automated patient reactivation",
    ),
    "legal_intake": (
        "AI intake and lead qualification for law firms",
        "law firms",
        "new-client screening",
        "automated legal intake",
    ),
    "legal_drafting": (
        "AI document drafting for law firms",
        "law firms",
        "manual legal document drafting",
        "assisted document generation",
    ),
    "legal_billing": (
        "Legal billing and collections automation",
        "law firms",
        "billing and overdue collections",
        "automated legal billing follow-up",
    ),
    "property_tenant": (
        "AI tenant inquiry support for property managers",
        "property managers",
        "repetitive resident questions",
        "automated tenant communications",
    ),
    "property_maintenance": (
        "Property maintenance triage and dispatch automation",
        "property managers",
        "maintenance request triage",
        "automated vendor assignment",
    ),
    "property_leasing": (
        "AI leasing lead qualification for property managers",
        "property managers",
        "manual leasing inquiry qualification",
        "automated leasing follow-up",
    ),
    "ecommerce_support": (
        "AI customer support for ecommerce stores",
        "ecommerce stores",
        "repetitive customer questions",
        "automated customer support",
    ),
    "ecommerce_cart": (
        "Abandoned checkout recovery for ecommerce stores",
        "ecommerce stores",
        "abandoned checkouts",
        "automated cart recovery",
    ),
    "ecommerce_reviews": (
        "Customer review generation for ecommerce stores",
        "ecommerce stores",
        "low review collection",
        "automated review requests",
    ),
    "bookkeeping_invoice": (
        "Invoice data extraction for bookkeeping teams",
        "bookkeeping teams",
        "manual invoice entry",
        "automated document extraction",
    ),
    "bookkeeping_cashflow": (
        "AI cash-flow advisory for small businesses",
        "small businesses",
        "limited cash-flow visibility",
        "automated cash-flow guidance",
    ),
    "veterinary_reception": (
        "AI receptionist for veterinary clinics",
        "veterinary clinics",
        "missed calls and appointment booking",
        "automated front desk",
    ),
    "hvac_reception": (
        "AI receptionist and quote booking for HVAC companies",
        "HVAC companies",
        "missed service calls and quote booking",
        "automated front desk",
    ),
}

EXPECTED = {
    "dental_insurance": "dental_insurance",
    "dental_recall": "dental_recall",
    "legal_drafting": "legal_drafting",
    "legal_billing": "legal_billing",
    "property_maintenance": "property_maintenance",
    "property_leasing": "property_leasing",
    "ecommerce_cart": "ecommerce_cart",
    "ecommerce_reviews": "ecommerce_reviews",
    "bookkeeping_invoice": "bookkeeping_invoice",
    "bookkeeping_cashflow": "bookkeeping_cashflow",
    "veterinary_reception": "veterinary_reception",
    "hvac_reception": "hvac_reception",
}

SIGNAL_SELECTORS = {
    "dental_insurance": "insurance",
    "dental_recall": "recall",
    "legal_drafting": "legal processes",
    "legal_billing": "billing",
    "property_maintenance": "maintenance",
    "property_leasing": "qualif",
    "ecommerce_cart": "recover returning shoppers",
    "bookkeeping_invoice": "invoice",
    "veterinary_reception": "appointment booking",
    "hvac_reception": "ai receptionist",
}

LOW_OVERLAP = [
    ("low_dental_frontdesk", "virtual front desk for oral care offices", "dental_reception"),
    ("low_dental_calls", "24/7 patient phone assistant", "dental_reception"),
    ("low_legal_screening", "prospective-client screening bot", "legal_intake"),
    ("low_legal_phone", "new-client phone gatekeeper", "legal_intake"),
    (
        "low_property_resident",
        "resident support assistant for building questions",
        "property_tenant",
    ),
    ("low_property_comms", "building occupant communications automation", "property_tenant"),
]

TRANSLATION_FIELDS = [
    "The product is positioned for prospective-client intake and screening.",
    "The assistant may collect a retainer and communicate case status.",
    "The resident assistant triages maintenance and assigns a vendor.",
    "The tenant asks about amenity access.",
    "The agent hands off complex requests and escalates urgent cases.",
    "The vendor claims it recovers abandoned checkouts and supports upsells.",
    "The workflow categorizes transactions and reconciles the ledger.",
    "The assistant supports month-end close and cash-flow review.",
    "The dental front desk handles recall and appointment leads.",
    "The tool is presented as automating insurance verification.",
    "QuickBooks is used for bookkeeping reconciliation.",
    "Shopify remains the source of order-status data.",
    "The AI receptionist is positioned as collecting prospective-client information.",
    "The creator claims the service can route maintenance requests.",
    "The product may recommend items before a human handoff.",
    "The channel offers paid consulting through an affiliate link.",
    "The featured SaaS product charges a monthly subscription.",
    "The platform uses n8n and speech recognition.",
    "The receptionist answers incoming calls and books appointments.",
    "The agent checks order status for ecommerce customers.",
    "The leasing assistant qualifies prospective residents.",
    "The law firm uses AI-assisted document drafting.",
    "The bookkeeping team extracts invoice data.",
    "The HVAC assistant schedules quote visits.",
]

MAX_VIDEOS = 14
MAX_SIGNAL_INPUTS = 12
MAX_NORMALIZER_CASES = 15
MAX_TRANSLATION_FIELDS = 24


def args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--normalizer-only", action="store_true")
    parser.add_argument("--evaluate-only", action="store_true")
    return parser.parse_args()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def candidate(candidate_id: str) -> dict:
    name, customer, problem, solution = CANDIDATES[candidate_id]
    return {
        "opportunity_id": str(uuid5(NAMESPACE_URL, f"semantic:{candidate_id}")),
        "name": name,
        "one_line_thesis": None,
        "industry": customer,
        "customer_type": customer,
        "problem": problem,
        "solution": solution,
        "status": "candidate",
    }


def lexical_terms(text: str) -> list[str]:
    return sorted({word for word in re.findall(r"[\w-]{3,}", text.lower()) if not word.isdigit()})[
        :20
    ]


def retrieve(text: str) -> list[dict]:
    terms = lexical_terms(text)
    ranked = []
    for key in CANDIDATES:
        item = candidate(key)
        haystack = " ".join(str(value or "").lower() for value in item.values())
        score = sum(term in haystack for term in terms)
        if score:
            ranked.append({"candidate_id": key, "score": score, **item})
    return sorted(ranked, key=lambda item: (-item["score"], item["name"].lower()))[:10]


def classify_outcome(case: dict, version: str) -> dict:
    """Attribute a case outcome to one primary layer."""
    if not case["retrieval"]["retrieved"]:
        return {"verdict": "missed_merge", "root_cause": "retrieval_failure"}
    output = case["versions"][version]["output"]
    if output["action"] == "REVIEW":
        return {"verdict": "review_appropriate", "root_cause": "ambiguous_ground_truth"}
    if output["action"] == "MATCH" and output["opportunity_id"] != case["expected_opportunity_id"]:
        return {"verdict": "false_merge", "root_cause": "normalizer_failure"}
    if output["action"] == "CREATE":
        return {"verdict": "missed_merge", "root_cause": "normalizer_failure"}
    return {"verdict": "correct_match", "root_cause": None}


async def generate(ai, *, task, model, prompt, payload, output_model):
    try:
        response = await ai.structured_generate(
            task_type=task,
            model=model,
            system_prompt=prompt,
            input_data=payload,
            output_model=output_model,
        )
    except ValidationError as error:
        return {
            "status": "invalid_output",
            "error_type": type(error).__name__,
            "prompt_hash": digest(prompt),
        }
    return {
        "status": "completed",
        "model": response.model,
        "provider": response.provider,
        "prompt_hash": digest(prompt),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "output": response.parsed.model_dump(mode="json"),
    }


def signal_payload(video, channel):
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


def normalizer_payload(
    case_id: str, statement: str, expected: str, ranked: list[dict], source_title: str
) -> dict:
    return {
        "signal": {
            "signal_id": str(uuid5(NAMESPACE_URL, f"semantic-signal:{case_id}")),
            "signal_type": "workflow",
            "statement": statement,
            "evidence_text": statement,
            "industry": None,
            "sub_industry": None,
            "customer_type": None,
            "problem": None,
            "solution": None,
            "business_model": None,
            "technology": [],
            "claim_status": "creator_claim",
            "observed_at": None,
        },
        "source_context": {"source_type": "validation_case", "title": source_title},
        "candidates": [
            {key: value for key, value in item.items() if key != "candidate_id" and key != "score"}
            for item in ranked
        ],
        "expected_opportunity_id": candidate(expected)["opportunity_id"],
    }


def build_normalizer_cases(result: dict) -> list[tuple[str, str, str, str, str]]:
    source_titles = {item["case_id"]: item.get("title", "") for item in result["sources"]}
    cases = []
    for item in result["signal_ab"]:
        expected = EXPECTED.get(item["case_id"])
        output = item["versions"]["v002"]
        selector = SIGNAL_SELECTORS.get(item["case_id"])
        if not expected or not selector or output["status"] != "completed":
            continue
        signal = next(
            (
                value
                for value in output["output"]["signals"]
                if selector in value["statement"].lower()
            ),
            None,
        )
        if signal is not None:
            cases.append(
                (
                    item["case_id"],
                    signal["statement"],
                    expected,
                    "real_source",
                    source_titles[item["case_id"]],
                )
            )
    cases.extend(
        (*case, "carefully_selected_low_overlap", "Carefully selected source phrase")
        for case in LOW_OVERLAP
    )
    return cases[:MAX_NORMALIZER_CASES]


async def run_normalizers(result: dict, destination: Path, ai, model: str) -> None:
    result["retrieval_normalizer_ab"] = []
    for case_id, statement, expected, family, source_title in build_normalizer_cases(result):
        ranked = retrieve(statement)
        expected_id = candidate(expected)["opportunity_id"]
        rank = next(
            (
                index
                for index, item in enumerate(ranked, 1)
                if item["opportunity_id"] == expected_id
            ),
            None,
        )
        payload = normalizer_payload(case_id, statement, expected, ranked, source_title)
        item = {
            "case_id": case_id,
            "family": family,
            "input_text": statement,
            "source_title": source_title,
            "expected_candidate": expected,
            "expected_opportunity_id": expected_id,
            "retrieval": {
                "terms": lexical_terms(statement),
                "rank": rank,
                "retrieved": rank is not None,
                "classification": "retrieval_success"
                if rank and rank <= 3
                else "retrieval_weak"
                if rank
                else "retrieval_failure",
                "ranked_candidates": ranked,
            },
            "versions": {},
        }
        if rank is None:
            item["root_cause"] = "retrieval_failure"
        else:
            for version in ("v001", "v002"):
                item["versions"][version] = await generate(
                    ai,
                    task="semantic_normalizer_ab",
                    model=model,
                    prompt=load_prompt("opportunity-normalizer", version),
                    payload={
                        key: value
                        for key, value in payload.items()
                        if key != "expected_opportunity_id"
                    },
                    output_model=OpportunityNormalizerOutput,
                )
        item["evaluation"] = {
            version: classify_outcome(item, version)
            for version in ("v001", "v002")
            if version in item["versions"]
        }
        result["retrieval_normalizer_ab"].append(item)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


async def run(destination: Path, *, normalizer_only: bool = False, evaluate_only: bool = False):
    if evaluate_only:
        result = json.loads(destination.read_text())
        for item in result["retrieval_normalizer_ab"]:
            item["evaluation"] = {
                version: classify_outcome(item, version)
                for version in ("v001", "v002")
                if version in item["versions"]
            }
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return
    settings = Settings()
    youtube = YouTubeClient(settings.youtube_api_key.get_secret_value())
    ai = OpenAIClient(
        settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
    )
    if normalizer_only:
        result = json.loads(destination.read_text())
        await run_normalizers(result, destination, ai, settings.ai_model_opportunity_normalization)
        await youtube.aclose()
        return
    result = {
        "limits": {
            "videos": MAX_VIDEOS,
            "signal_inputs": MAX_SIGNAL_INPUTS,
            "normalizer_cases": MAX_NORMALIZER_CASES,
            "translation_fields": MAX_TRANSLATION_FIELDS,
            "provider_calls": 66,
        },
        "youtube_quota_estimate": 0,
        "sources": [],
        "signal_ab": [],
        "retrieval_normalizer_ab": [],
        "translation_ab": [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    try:
        discovered = []
        for case_id, query in SEARCH_CASES[:MAX_VIDEOS]:
            page = await youtube.search_videos(query, max_results=5)
            result["youtube_quota_estimate"] += 100
            if not page.items:
                result["sources"].append(
                    {"case_id": case_id, "query": query, "status": "insufficient_source_quality"}
                )
                checkpoint()
                continue
            hit = page.items[0]
            videos = await youtube.get_videos([hit.youtube_video_id])
            channels = await youtube.get_channels([hit.youtube_channel_id])
            result["youtube_quota_estimate"] += 2
            if not videos or not channels:
                continue
            video, channel = videos[0], channels[0]
            source = {
                "case_id": case_id,
                "query": query,
                "status": "selected",
                "video_id": video.youtube_video_id,
                "title": video.title,
                "channel_id": channel.youtube_channel_id,
                "channel": channel.name,
                "comment_count": video.comment_count,
                "description_length": len(video.description),
            }
            result["sources"].append(source)
            discovered.append((case_id, video, channel))
            checkpoint()

        for case_id, video, channel in discovered[:MAX_SIGNAL_INPUTS]:
            item = {"case_id": case_id, "video_id": video.youtube_video_id, "versions": {}}
            for version in ("v001", "v002"):
                item["versions"][version] = await generate(
                    ai,
                    task="semantic_signal_ab",
                    model=settings.ai_model_signal_extraction,
                    prompt=load_prompt("signal-extractor", version),
                    payload=signal_payload(video, channel),
                    output_model=BusinessSignalExtractorOutput,
                )
            result["signal_ab"].append(item)
            checkpoint()

        await run_normalizers(result, destination, ai, settings.ai_model_opportunity_normalization)

        for offset in range(0, MAX_TRANSLATION_FIELDS, 4):
            fields = TRANSLATION_FIELDS[offset : offset + 4]
            payload = {
                "canonical_locale": "en-US",
                "target_locale": "zh-CN",
                "entity_type": "semantic_validation",
                "fields": [
                    {"field_name": f"field_{offset + index}", "source_text": text}
                    for index, text in enumerate(fields, 1)
                ],
            }
            item = {"source_fields": fields, "versions": {}}
            for version in ("v001", "v002"):
                prompt = (
                    PROMPT_ROOT / "intelligence-translation" / "zh-CN" / f"{version}.md"
                ).read_text()
                item["versions"][version] = await generate(
                    ai,
                    task="semantic_translation_ab",
                    model=settings.intelligence_translation_model,
                    prompt=prompt,
                    payload=payload,
                    output_model=IntelligenceTranslationOutput,
                )
            result["translation_ab"].append(item)
            checkpoint()
    finally:
        await youtube.aclose()


if __name__ == "__main__":
    options = args()
    asyncio.run(
        run(
            options.output,
            normalizer_only=options.normalizer_only,
            evaluate_only=options.evaluate_only,
        )
    )
