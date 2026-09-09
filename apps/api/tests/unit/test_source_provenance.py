import pytest

from ai_business_radar_api.services.source_provenance import source_navigation


@pytest.mark.parametrize("video_id", [None, "", "bad/id", "javascript:alert(1)", "x" * 12])
def test_source_navigation_never_uses_model_text_or_invalid_video_ids(video_id):
    result = source_navigation(
        {
            "youtube_video_id": video_id,
            "statement": "https://www.youtube.com/watch?v=abcdefghijk",
            "evidence_text": "https://www.youtube.com/watch?v=abcdefghijk",
            "stored_source_url": "https://untrusted.example/",
            "evidence_kind": "linked_signal",
        }
    )
    assert result == {"source_url": None, "source_navigation": "unavailable"}


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "//example.org",
        "https://u:p@example.org",
        "https://",
        "https://[bad",
        "https://example.org/ a",
    ],
)
def test_explicit_urls_reject_unsafe_navigation(url):
    assert (
        source_navigation(
            {"stored_source_url": url, "evidence_kind": "explicit", "source_type": "manual"}
        )["source_url"]
        is None
    )
