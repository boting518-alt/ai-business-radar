"""Public navigation derived from persisted provenance, never from extracted text."""

import re
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel


class SourceProvenance(BaseModel):
    source_video_id: UUID | None = None
    youtube_video_id: str | None = None
    video_title: str | None = None
    channel_name: str | None = None
    source_comment_id: UUID | None = None
    youtube_comment_id: str | None = None
    source_comment_text: str | None = None
    source_url: str | None = None
    # Navigable is not a claim that the remote source is still available.
    source_navigation: str = "unavailable"


def source_navigation(values: dict) -> dict:
    video_id = values.get("youtube_video_id")
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return {
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "source_navigation": "parent_video" if values.get("source_comment_id") else "video",
        }
    # Only standalone editorial records may use their persisted external URL.
    stored = values.get("stored_source_url")
    if (
        values.get("evidence_kind") == "explicit"
        and values.get("source_type") == "manual"
        and stored
    ):
        try:
            parsed = urlsplit(stored)
            if (
                parsed.scheme in {"https", "http"}
                and parsed.hostname
                and not (parsed.username or parsed.password or any(c.isspace() for c in stored))
            ):
                return {"source_url": stored, "source_navigation": "external"}
        except ValueError:
            pass
    return {"source_url": None, "source_navigation": "unavailable"}
