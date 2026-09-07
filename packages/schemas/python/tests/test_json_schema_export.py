import json
from pathlib import Path

from ai_business_radar_schemas.ai_outputs import AI_OUTPUT_MODELS
from scripts.export_ai_json_schemas import export_schemas

CHECKED_IN_SCHEMA_DIRECTORY = Path(__file__).resolve().parents[2] / "json"


def test_all_ai_json_schemas_are_generated_from_models(tmp_path: Path) -> None:
    written = export_schemas(tmp_path)

    assert {path.name for path in written} == {
        "relevance_filter.v001.schema.json",
        "signal_extractor.v001.schema.json",
        "comment_pain_miner.v001.schema.json",
        "opportunity_normalizer.v001.schema.json",
        "hype_detector.v001.schema.json",
        "intelligence_translation.v001.schema.json",
    }

    for task_name, model in AI_OUTPUT_MODELS.items():
        path = tmp_path / f"{task_name}.v001.schema.json"
        assert json.loads(path.read_text(encoding="utf-8")) == model.model_json_schema(
            mode="validation"
        )


def test_checked_in_ai_json_schemas_match_authoritative_models() -> None:
    for task_name, model in AI_OUTPUT_MODELS.items():
        path = CHECKED_IN_SCHEMA_DIRECTORY / f"{task_name}.v001.schema.json"
        assert json.loads(path.read_text(encoding="utf-8")) == model.model_json_schema(
            mode="validation"
        )
