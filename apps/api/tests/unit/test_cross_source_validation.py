import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ARTIFACT = ROOT / "artifacts/cross-source-validation/20260907T173000Z/cases.json"
SCRIPT = ROOT / "apps/api/scripts/validate_cross_source.py"
FIXTURE = ROOT / "tests/fixtures/cross_source_validation/regression-cases.json"


def load_script():
    spec = importlib.util.spec_from_file_location("validate_cross_source", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validation_dataset_is_bounded_and_source_diverse() -> None:
    data = json.loads(ARTIFACT.read_text())
    assert data["limits"]["videos"] == 20
    assert data["limits"]["search_requests"] == 5
    assert sum(map(len, data["sources"].values())) == 20
    assert len(data["sources"]) == 5
    for sources in data["sources"].values():
        assert len(sources) == 4
        assert len({source["channel_id"] for source in sources}) == 4


def test_candidate_stress_matches_expected_clusters_without_cross_vertical_merges() -> None:
    data = json.loads(ARTIFACT.read_text())
    assert len(data["normalizer_ab"]) == 10
    for case in data["normalizer_ab"]:
        assert case["candidate_count"] == 5
        for version in ("v001", "v002"):
            output = case["versions"][version]["output"]
            assert output["action"] == "MATCH"
            assert output["opportunity_id"] == case["expected_opportunity_id"]


def test_lexical_replay_ranks_expected_candidate_first() -> None:
    data = json.loads(ARTIFACT.read_text())
    replay = load_script().lexical_candidate_review(data)
    assert len(replay) == 10
    assert all(case["expected_rank"] == 1 for case in replay)
    assert replay == data["lexical_candidate_review"]


def test_provider_schema_failure_and_real_regressions_are_retained() -> None:
    data = json.loads(ARTIFACT.read_text())
    statuses = [
        case["versions"][version]["status"]
        for case in data["signal_ab"]
        for version in ("v001", "v002")
    ]
    assert statuses.count("invalid_output") == 1
    fixture = json.loads(FIXTURE.read_text())
    assert {case["human_verdict"] for case in fixture} >= {
        "observed_minor_issue",
        "observed_major_issue_v001",
    }


def test_translation_preserves_cross_domain_terms_and_claim_attribution() -> None:
    data = json.loads(ARTIFACT.read_text())
    translated = " ".join(
        field["translated_text"]
        for group in data["translation_ab"]
        for field in group["versions"]["v002"]["output"]["translations"]
    )
    for term in ("租户", "Shopify", "QuickBooks", "MagicDoor"):
        assert term in translated
    assert "声称" in translated or "宣传称" in translated
