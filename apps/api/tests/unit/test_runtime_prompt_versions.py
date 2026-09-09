from pathlib import Path

import pytest

from ai_business_radar_api.infrastructure.ai import (
    RUNTIME_PROMPT_DEFAULTS,
    PromptNotFoundError,
    resolve_prompt,
)


def test_runtime_matrix_preserves_independent_stage_versions() -> None:
    assert RUNTIME_PROMPT_DEFAULTS == {
        "relevance-filter": "v001",
        "opportunity-consolidation": "v002",
        "signal-extractor": "v003",
        "comment-pain-miner": "v001",
        "opportunity-normalizer": "v001",
        "intelligence-translation/zh-CN": "v001",
    }


def test_signal_prompt_history_hashes_are_immutable() -> None:
    assert {
        version: resolve_prompt("signal-extractor", version).sha256
        for version in ("v001", "v002", "v003")
    } == {
        "v001": "e129d096c32b51356fd5a2280f80877a21759b70b0e4fa5d9c05b7bc945ff641",
        "v002": "a87c62b333f02928f432b100655feff34d1251f6163da776d586430db9d7e16c",
        "v003": "d91be041c6f50c0f97f5c9ba9d3469778ba92f1ee91d7063531df003a1c792e3",
    }


def test_explicit_version_resolution_supports_rollback_and_rejects_unknown(tmp_path: Path) -> None:
    assert resolve_prompt("signal-extractor", "v001").version == "v001"
    with pytest.raises(PromptNotFoundError, match="Invalid prompt version"):
        resolve_prompt("signal-extractor", "v999", root=tmp_path)


def test_used_consolidation_prompt_history_is_immutable() -> None:
    assert resolve_prompt("opportunity-consolidation", "v001").sha256 == (
        "2f35b735fa2127726fa54d8b1353c9f30208a20773064a4da52083b3950288bd"
    )
    assert resolve_prompt("opportunity-consolidation").version == "v002"
