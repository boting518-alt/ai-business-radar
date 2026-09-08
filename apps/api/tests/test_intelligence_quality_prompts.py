import hashlib
import json
from pathlib import Path

from ai_business_radar_api.services import opportunity_normalization, signal_extraction
from ai_business_radar_api.services.intelligence_localization import (
    CURRENT_TRANSLATION_VERSIONS,
)
from ai_business_radar_api.services.intelligence_translation import TRANSLATION_VERSION

ROOT = Path(__file__).parents[3]
PROMPTS = ROOT / "prompts"
FIXTURES = ROOT / "tests" / "fixtures" / "intelligence_quality"
AB_RESULTS = ROOT / "artifacts" / "intelligence-quality" / "20260907T171231Z" / "ab-results.json"
V003_REPORT = ROOT / "artifacts" / "prompt-fix" / "20260908T093000Z" / "signal-v003-ab.md"

V001_HASHES = {
    "signal-extractor/v001.md": "e129d096c32b51356fd5a2280f80877a21759b70b0e4fa5d9c05b7bc945ff641",
    "opportunity-normalizer/v001.md": (
        "121ac95b41c1dda27708212fff87e480fda3f850f240067b362888a31a068f9f"
    ),
    "intelligence-translation/zh-CN/v001.md": (
        "1519c6cb9aa7569db5988f45119769ea8595b509cecac7c3df3c01bcb1edb28e"
    ),
}


def test_v001_prompts_remain_byte_for_byte_immutable():
    for relative, expected in V001_HASHES.items():
        assert hashlib.sha256((PROMPTS / relative).read_bytes()).hexdigest() == expected


def test_v002_prompts_encode_observed_quality_controls():
    signal = (PROMPTS / "signal-extractor/v002.md").read_text()
    normalizer = (PROMPTS / "opportunity-normalizer/v002.md").read_text()
    translation = (PROMPTS / "intelligence-translation/zh-CN/v002.md").read_text()
    normalized_signal = " ".join(signal.split())

    assert "One signal expresses one assertion" in signal
    assert "generic heading" in normalized_signal and "not by itself" in normalized_signal
    assert "not customer demand" in normalized_signal
    assert "Keep customer scope conservative" in signal
    assert "repeatable commercial pattern" in normalizer
    assert "vendor-neutral" in normalizer and "duplicate" in normalizer
    assert "mirroring English word order" in translation
    assert "claims" in translation and "may" in translation
    assert "VitalDesk" in translation and "appointment lead" in translation


def test_v002_is_experimental_and_does_not_change_runtime_defaults():
    assert signal_extraction.PROMPT_VERSION == "v003"
    assert opportunity_normalization.PROMPT_VERSION == "v001"
    assert TRANSLATION_VERSION == "translation-zh-CN-v001"
    assert CURRENT_TRANSLATION_VERSIONS == {"zh-CN": "translation-zh-CN-v001"}


def test_promoted_v003_encodes_permanent_signal_regressions():
    prompt = " ".join((PROMPTS / "signal-extractor/v003.md").read_text().split()).lower()
    for phrase in (
        "business behavior as `workflow`",
        "enabling mechanism as `technology`",
        "attribute monetization to its actual owner",
        "cta",
        "community size",
        "not automatically the featured product's customer base",
        "keep tightly coupled substeps together",
        "keep buyer scope exact",
        "preserve vendor/creator attribution",
        "pricing: null",
        "never use numeric zero as a placeholder",
    ):
        assert phrase in prompt
    report = V003_REPORT.read_text()
    assert "PD2eKTzkZ70" in report and "schema-invalid under v002" in report
    assert "completed under v003" in report and "pricing: null" in report


def test_quality_fixtures_are_bounded_semantic_contracts():
    names = {
        "signal-quality-cases.json": 4,
        "opportunity-quality-cases.json": 2,
        "translation-quality-cases.json": 3,
    }
    for name, expected_count in names.items():
        payload = json.loads((FIXTURES / name).read_text())
        assert payload["version"] == "v001"
        assert len(payload["cases"]) == expected_count
        assert len({case["id"] for case in payload["cases"]}) == expected_count
        for case in payload["cases"]:
            assert case["input"]
            assert case["expected_properties"]
            assert case["forbidden_behavior"]


def test_recorded_ab_outputs_address_observed_regressions():
    comparisons = json.loads(AB_RESULTS.read_text())["comparisons"]
    signal_v002 = comparisons["signal_extractor"]["v002"]["output"]["signals"]
    assert all(item["claim_status"] == "creator_claim" for item in signal_v002)
    assert next(item for item in signal_v002 if "free audit" in item["statement"])["type"] == (
        "distribution"
    )

    normalizer_v002 = comparisons["opportunity_normalizer"]["v002"]["output"]
    assert normalizer_v002["action"] == "MATCH"
    assert "dental practices" in normalizer_v002["canonical_name"].lower()
    assert "VitalDesk" not in normalizer_v002["canonical_name"]

    translations = comparisons["translation"]["v002"]
    translated_text = [
        field["translated_text"] for run in translations for field in run["output"]["translations"]
    ]
    assert "VitalDesk" in translated_text[0]
    assert "线索" in translated_text[0] and "潜在客户" not in translated_text[0]
    assert all("在线索 VitalDesk" not in text for text in translated_text)
    assert "定位" in translated_text[1]
    assert "可以" in translated_text[2]
