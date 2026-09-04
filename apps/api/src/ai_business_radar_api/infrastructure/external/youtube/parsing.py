"""Conservative parsing from YouTube wire payloads to typed DTOs."""

from datetime import datetime, timedelta
from typing import Any

import isodate
from pydantic import ValidationError

from .errors import YouTubeResponseValidationError
from .models import (
    YouTubeChannel,
    YouTubeComment,
    YouTubeCommentPage,
    YouTubePageInfo,
    YouTubeSearchItem,
    YouTubeSearchPage,
    YouTubeVideo,
)


def _thumbnail(snippet: dict[str, Any]) -> str | None:
    thumbnails = snippet.get("thumbnails", {})
    for name in ("maxres", "standard", "high", "medium", "default"):
        if url := thumbnails.get(name, {}).get("url"):
            return str(url)
    return None


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def parse_duration_seconds(value: str) -> int:
    try:
        duration = isodate.parse_duration(value)
        if not isinstance(duration, timedelta):
            duration = duration.totimedelta(start=datetime(1970, 1, 1))
        return int(duration.total_seconds())
    except (TypeError, ValueError, OverflowError) as error:
        raise YouTubeResponseValidationError("YouTube returned an invalid duration") from error


def _validated(model: type[Any], values: dict[str, Any]) -> Any:
    try:
        return model.model_validate(values)
    except (ValidationError, TypeError, ValueError) as error:
        raise YouTubeResponseValidationError("YouTube returned an invalid response") from error


def parse_search_page(payload: dict[str, Any]) -> YouTubeSearchPage:
    try:
        items = []
        for item in payload["items"]:
            snippet = item["snippet"]
            items.append(
                _validated(
                    YouTubeSearchItem,
                    {
                        "youtube_video_id": item["id"]["videoId"],
                        "youtube_channel_id": snippet["channelId"],
                        "title": snippet["title"],
                        "description": snippet.get("description", ""),
                        "published_at": snippet["publishedAt"],
                        "channel_title": snippet["channelTitle"],
                        "thumbnail_url": _thumbnail(snippet),
                    },
                )
            )
        page_info_raw = payload.get("pageInfo")
        page_info = (
            None
            if page_info_raw is None
            else _validated(
                YouTubePageInfo,
                {
                    "total_results": page_info_raw.get("totalResults"),
                    "results_per_page": page_info_raw.get("resultsPerPage"),
                },
            )
        )
        return YouTubeSearchPage(
            items=items,
            next_page_token=payload.get("nextPageToken"),
            prev_page_token=payload.get("prevPageToken"),
            page_info=page_info,
        )
    except (KeyError, TypeError) as error:
        raise YouTubeResponseValidationError(
            "YouTube returned an invalid search response"
        ) from error


def parse_videos(payload: dict[str, Any]) -> list[YouTubeVideo]:
    try:
        videos = []
        for item in payload["items"]:
            snippet = item["snippet"]
            details = item["contentDetails"]
            statistics = item.get("statistics", {})
            videos.append(
                _validated(
                    YouTubeVideo,
                    {
                        "youtube_video_id": item["id"],
                        "youtube_channel_id": snippet["channelId"],
                        "title": snippet["title"],
                        "description": snippet.get("description", ""),
                        "published_at": snippet["publishedAt"],
                        "category_id": snippet.get("categoryId"),
                        "language": snippet.get("defaultLanguage")
                        or snippet.get("defaultAudioLanguage"),
                        "duration_seconds": parse_duration_seconds(details["duration"]),
                        "thumbnail_url": _thumbnail(snippet),
                        "view_count": _optional_int(statistics.get("viewCount")),
                        "like_count": _optional_int(statistics.get("likeCount")),
                        "comment_count": _optional_int(statistics.get("commentCount")),
                        "has_captions": {"true": True, "false": False}.get(details.get("caption")),
                    },
                )
            )
        return videos
    except (KeyError, TypeError, ValueError) as error:
        raise YouTubeResponseValidationError(
            "YouTube returned an invalid videos response"
        ) from error


def parse_channels(payload: dict[str, Any]) -> list[YouTubeChannel]:
    try:
        channels = []
        for item in payload["items"]:
            snippet = item["snippet"]
            statistics = item.get("statistics", {})
            subscribers = (
                None
                if statistics.get("hiddenSubscriberCount")
                else _optional_int(statistics.get("subscriberCount"))
            )
            channels.append(
                _validated(
                    YouTubeChannel,
                    {
                        "youtube_channel_id": item["id"],
                        "name": snippet["title"],
                        "description": snippet.get("description", ""),
                        "country": snippet.get("country"),
                        "subscriber_count": subscribers,
                        "video_count": _optional_int(statistics.get("videoCount")),
                        "view_count": _optional_int(statistics.get("viewCount")),
                    },
                )
            )
        return channels
    except (KeyError, TypeError, ValueError) as error:
        raise YouTubeResponseValidationError(
            "YouTube returned an invalid channels response"
        ) from error


def parse_comment_page(payload: dict[str, Any]) -> YouTubeCommentPage:
    try:
        items = []
        for item in payload["items"]:
            thread = item["snippet"]
            comment = thread["topLevelComment"]
            snippet = comment["snippet"]
            items.append(
                _validated(
                    YouTubeComment,
                    {
                        "youtube_comment_id": comment["id"],
                        "video_id": snippet["videoId"],
                        "text": snippet.get("textOriginal", snippet.get("textDisplay", "")),
                        "published_at": snippet["publishedAt"],
                        "updated_at": snippet.get("updatedAt"),
                        "like_count": _optional_int(snippet.get("likeCount")),
                        "reply_count": _optional_int(thread.get("totalReplyCount")),
                    },
                )
            )
        return YouTubeCommentPage(items=items, next_page_token=payload.get("nextPageToken"))
    except (KeyError, TypeError, ValueError) as error:
        raise YouTubeResponseValidationError(
            "YouTube returned an invalid comments response"
        ) from error
