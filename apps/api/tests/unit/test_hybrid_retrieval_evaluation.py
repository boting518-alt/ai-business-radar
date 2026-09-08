import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from ai_business_radar_api.services import opportunity_normalization, signal_extraction
from ai_business_radar_api.services.intelligence_localization import CURRENT_TRANSLATION_VERSIONS
from ai_business_radar_api.services.intelligence_translation import TRANSLATION_VERSION

ROOT = Path(__file__).resolve().parents[4]
ARTIFACT = ROOT / "artifacts/hybrid-retrieval/20260908T093000Z/retrieval-cases.json"
SCRIPT = ROOT / "apps/api/scripts/evaluate_hybrid_retrieval.py"
PROMPTS = ROOT / "prompts"


def data():
    return json.loads(ARTIFACT.read_text())


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("hybrid_evaluation", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def test_lexical_baseline_reproduces_task_037_metrics() -> None:
    metrics = data()["metrics"]["lexical"]
    assert metrics["recall_at_1"] == 0.6
    assert metrics["recall_at_3"] == 0.8
    assert metrics["recall_at_5"] == 14 / 15


def test_semantic_and_hybrid_recover_low_overlap_dental_case() -> None:
    artifact = data()
    case = next(case for case in artifact["cases"] if case["case_id"] == "low_dental_calls")
    assert "dental_reception" not in case["lexical"]
    assert "dental_reception" in case["semantic"]
    assert "dental_reception" in case["weighted_best"][:3]
    assert artifact["metrics"]["low_overlap"]["weighted_best"]["recall_at_5"] == 1.0


def test_hybrid_sets_are_bounded_unique_and_deterministic() -> None:
    artifact = data()
    assert artifact["limits"]["union_limit"] == 10
    for case in artifact["cases"]:
        assert len(case["union"]) <= 10
        assert len(case["union"]) == len(set(case["union"]))
        assert len(case["weighted_best"]) == len(set(case["weighted_best"]))
    assert module().cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_hard_negative_positive_is_above_named_negatives() -> None:
    artifact = data()
    fixtures = json.loads(
        (ROOT / "tests/fixtures/hybrid_retrieval/hard-negatives.json").read_text()
    )
    cases = {case["case_id"]: case for case in artifact["cases"]}
    passed = 0
    for fixture in fixtures:
        ranked = cases[fixture["query_case"]]["semantic"]
        positive_rank = ranked.index(fixture["positive"])
        if all(
            negative not in ranked or positive_rank < ranked.index(negative)
            for negative in fixture["negatives"]
        ):
            passed += 1
    assert passed >= 7


def test_normalizer_receives_bounded_union_without_false_match() -> None:
    for case in data()["normalizer_hybrid_ab"]:
        assert len(case["candidate_ids"]) <= 10
        assert len(case["candidate_ids"]) == len(set(case["candidate_ids"]))
        for version in ("v001", "v002"):
            output = case["versions"][version]["output"]
            assert output["action"] in {"MATCH", "REVIEW"}
            if output["action"] == "MATCH":
                assert output["opportunity_id"] == case["expected_opportunity_id"]


def test_signal_v003_is_schema_valid_and_fixes_invoice_case() -> None:
    artifact = data()
    invoice = next(case for case in artifact["signal_v003_ab"] if case["video_id"] == "PD2eKTzkZ70")
    assert invoice["versions"]["v002"]["status"] == "invalid_output"
    assert invoice["versions"]["v003"]["status"] == "completed"
    assert all(
        case["versions"]["v003"]["status"] == "completed" for case in artifact["signal_v003_ab"]
    )


def test_signal_v003_improves_category_monetization_and_fragmentation_cases() -> None:
    artifact = data()
    by_video = {case["video_id"]: case for case in artifact["signal_v003_ab"]}
    legal = by_video["0c6AJl7z-Ic"]["versions"]["v003"]["output"]["signals"]
    assert any(
        item["type"] == "workflow" and "analyze invoices" in item["statement"] for item in legal
    )
    community = by_video["5DevfwAfVpA"]["versions"]["v003"]["output"]["signals"]
    assert any(
        item["type"] == "distribution" and "community" in item["statement"] for item in community
    )
    assert not any(
        item["type"] in {"customer", "adoption"} and "community" in item["statement"]
        for item in community
    )
    sales = by_video["swpwrSZdAJ4"]["versions"]["v003"]["output"]["signals"]
    assert sum("sales" in item["statement"].lower() for item in sales) <= 2


def test_translation_v003_handles_creator_retainer_terms_and_claims() -> None:
    outputs = [
        field["translated_text"]
        for group in data()["translation_v003_ab"]
        for field in group["versions"]["v003"]["output"]["translations"]
    ]
    text = " ".join(outputs)
    assert "创作者" in text and "创建者" not in text
    assert "预付律师费" in text
    assert "转交人工" in text
    assert "患者召回" in text
    assert "供应商声称" in text


def test_new_prompts_do_not_switch_runtime_or_mutate_old_prompts() -> None:
    hashes = {
        "signal-extractor/v001.md": (
            "e129d096c32b51356fd5a2280f80877a21759b70b0e4fa5d9c05b7bc945ff641"
        ),
        "signal-extractor/v002.md": (
            "a87c62b333f02928f432b100655feff34d1251f6163da776d586430db9d7e16c"
        ),
        "opportunity-normalizer/v001.md": (
            "121ac95b41c1dda27708212fff87e480fda3f850f240067b362888a31a068f9f"
        ),
        "opportunity-normalizer/v002.md": (
            "a7a8eb5c15ca4dbe4991e144732e7c99e45fc5b0dcd960b914bf35a79bc6d050"
        ),
        "intelligence-translation/zh-CN/v001.md": (
            "1519c6cb9aa7569db5988f45119769ea8595b509cecac7c3df3c01bcb1edb28e"
        ),
        "intelligence-translation/zh-CN/v002.md": (
            "b7b06f6bbed9189c6b688e4e5d07a34760e54efbe4d761a2ed2df4c40acc7044"
        ),
    }
    for relative, expected in hashes.items():
        assert hashlib.sha256((PROMPTS / relative).read_bytes()).hexdigest() == expected
    assert signal_extraction.PROMPT_VERSION == "v003"
    assert opportunity_normalization.PROMPT_VERSION == "v001"
    assert TRANSLATION_VERSION == "translation-zh-CN-v001"
    assert CURRENT_TRANSLATION_VERSIONS == {"zh-CN": "translation-zh-CN-v001"}
