import hashlib
import importlib.util
import json
from pathlib import Path

from ai_business_radar_api.services import opportunity_normalization, signal_extraction
from ai_business_radar_api.services.intelligence_localization import CURRENT_TRANSLATION_VERSIONS
from ai_business_radar_api.services.intelligence_translation import TRANSLATION_VERSION

ROOT = Path(__file__).resolve().parents[4]
ARTIFACT = ROOT / "artifacts/semantic-separation/20260908T020000Z/cases.json"
FIXTURES = ROOT / "tests/fixtures/semantic_separation"
SCRIPT = ROOT / "apps/api/scripts/validate_semantic_separation.py"


def module():
    spec = importlib.util.spec_from_file_location("semantic_validation", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def data():
    return json.loads(ARTIFACT.read_text())


def test_real_dataset_and_provider_work_are_bounded() -> None:
    value = data()
    assert len(value["sources"]) == 14 <= 25
    assert len(value["signal_ab"]) == 12 <= 20
    assert len(value["retrieval_normalizer_ab"]) == 15
    assert sum(len(group["source_fields"]) for group in value["translation_ab"]) == 24
    assert {source["case_id"] for source in value["sources"]} >= {
        "multilingual_ja_dental",
        "multilingual_zh_legal",
    }


def test_low_overlap_recall_exposes_a_real_lexical_failure() -> None:
    cases = [
        case
        for case in data()["retrieval_normalizer_ab"]
        if case["family"] == "carefully_selected_low_overlap"
    ]
    assert len(cases) == 6
    ranks = [case["retrieval"]["rank"] for case in cases]
    assert sum(rank == 1 for rank in ranks) == 4
    assert sum(rank is not None and rank <= 3 for rank in ranks) == 5
    assert sum(rank is not None and rank <= 5 for rank in ranks) == 5
    assert any(case.get("root_cause") == "retrieval_failure" for case in cases)


def test_retrieval_and_normalizer_failures_are_attributed_separately() -> None:
    classify = module().classify_outcome
    retrieval_failure = {
        "retrieval": {"retrieved": False},
        "versions": {},
        "expected_opportunity_id": "expected",
    }
    assert classify(retrieval_failure, "v002")["root_cause"] == "retrieval_failure"
    false_merge = {
        "retrieval": {"retrieved": True},
        "expected_opportunity_id": "expected",
        "versions": {"v002": {"output": {"action": "MATCH", "opportunity_id": "wrong"}}},
    }
    assert classify(false_merge, "v002") == {
        "verdict": "false_merge",
        "root_cause": "normalizer_failure",
    }


def test_same_industry_and_cross_buyer_cases_do_not_false_merge() -> None:
    artifact = data()
    cases = {case["case_id"]: case for case in artifact["retrieval_normalizer_ab"]}
    same_industry = json.loads((FIXTURES / "same_industry_different_workflow.json").read_text())
    for expected in same_industry:
        case = cases[expected["case_id"]]
        for version in ("v001", "v002"):
            output = case["versions"][version]["output"]
            assert output["action"] in {"MATCH", "REVIEW"}
            if output["action"] == "MATCH":
                assert output["opportunity_id"] == case["expected_opportunity_id"]
    for case_id in ("veterinary_reception", "hvac_reception"):
        assert (
            cases[case_id]["versions"]["v002"]["output"]["opportunity_id"]
            == cases[case_id]["expected_opportunity_id"]
        )


def test_real_category_and_monetization_regressions_remain_explicit() -> None:
    categories = json.loads((FIXTURES / "workflow_vs_technology.json").read_text())
    assert any(case.get("observed_v002") == "technology" for case in categories)
    monetization = json.loads((FIXTURES / "creator_vs_product_monetization.json").read_text())
    assert {case["owner"] for case in monetization} == {"creator", "featured_product"}
    fragmentation = json.loads((FIXTURES / "over_fragmentation.json").read_text())
    assert any(case["v002"] == "over_fragmented" for case in fragmentation)


def test_sparse_sources_do_not_invent_pricing_or_demand() -> None:
    artifact = data()
    sparse_ids = {
        case["video_id"] for case in json.loads((FIXTURES / "sparse_metadata.json").read_text())
    }
    for case in artifact["signal_ab"]:
        if case["video_id"] not in sparse_ids:
            continue
        signals = case["versions"]["v002"].get("output", {}).get("signals", [])
        assert not any(signal["type"] in {"purchase_intent", "demand"} for signal in signals)


def test_translation_terms_claims_and_proper_names_are_preserved() -> None:
    translations = " ".join(
        field["translated_text"]
        for group in data()["translation_ab"]
        for field in group["versions"]["v002"]["output"]["translations"]
    )
    for term in (
        "潜在客户",
        "维修",
        "供应商",
        "转交人工",
        "追加销售",
        "召回",
        "QuickBooks",
        "Shopify",
        "声称",
    ):
        assert term in translations


def test_v001_prompts_and_runtime_defaults_remain_immutable() -> None:
    expected = {
        "signal-extractor/v001.md": (
            "e129d096c32b51356fd5a2280f80877a21759b70b0e4fa5d9c05b7bc945ff641"
        ),
        "opportunity-normalizer/v001.md": (
            "121ac95b41c1dda27708212fff87e480fda3f850f240067b362888a31a068f9f"
        ),
        "intelligence-translation/zh-CN/v001.md": (
            "1519c6cb9aa7569db5988f45119769ea8595b509cecac7c3df3c01bcb1edb28e"
        ),
    }
    for relative, checksum in expected.items():
        assert hashlib.sha256((ROOT / "prompts" / relative).read_bytes()).hexdigest() == checksum
    assert signal_extraction.PROMPT_VERSION == "v003"
    assert opportunity_normalization.PROMPT_VERSION == "v001"
    assert TRANSLATION_VERSION == "translation-zh-CN-v001"
    assert CURRENT_TRANSLATION_VERSIONS == {"zh-CN": "translation-zh-CN-v001"}
