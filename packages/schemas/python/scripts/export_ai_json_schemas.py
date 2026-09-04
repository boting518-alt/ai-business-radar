"""Generate language-neutral JSON Schemas from authoritative Pydantic models."""

import json
from pathlib import Path

from ai_business_radar_schemas.ai_outputs import AI_OUTPUT_MODELS


OUTPUT_DIRECTORY = Path(__file__).resolve().parents[2] / "json"


def export_schemas(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for task_name, model in AI_OUTPUT_MODELS.items():
        output_path = output_directory / f"{task_name}.v001.schema.json"
        schema = model.model_json_schema(mode="validation")
        output_path.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(output_path)

    return written


if __name__ == "__main__":
    for path in export_schemas():
        print(path)
