from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from ai_business_radar_api.infrastructure.external.youtube import (
    YouTubeAPIError,
    YouTubeAuthenticationError,
    YouTubeClient,
    YouTubeQuotaCost,
    YouTubeQuotaExceededError,
    YouTubeRateLimitError,
    YouTubeResponseValidationError,
)
from ai_business_radar_api.infrastructure.external.youtube.parsing import parse_duration_seconds

API_KEY = "unit-test-api-key"
BASE_URL = "https://www.googleapis.com/youtube/v3/"


def search_payload(
    *, next_token: str | None = "next", previous_token: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "items": [
            {
                "id": {"videoId": "video-1"},
                "snippet": {
                    "channelId": "channel-1",
                    "title": "A video",
                    "description": "Description",
                    "publishedAt": "2026-01-02T03:04:05Z",
                    "channelTitle": "A channel",
                    "thumbnails": {"high": {"url": "https://img.test/high.jpg"}},
                },
            }
        ],
        "pageInfo": {"totalResults": 8, "resultsPerPage": 1},
    }
    if next_token:
        payload["nextPageToken"] = next_token
    if previous_token:
        payload["prevPageToken"] = previous_token
    return payload


def video_item(identifier: str = "video-1") -> dict[str, Any]:
    return {
        "id": identifier,
        "snippet": {
            "channelId": "channel-1",
            "title": "Video",
            "description": "Description",
            "publishedAt": "2026-01-02T03:04:05Z",
            "categoryId": "28",
            "defaultAudioLanguage": "en",
            "thumbnails": {},
        },
        "contentDetails": {"duration": "PT1H2M3S", "caption": "true"},
        "statistics": {"viewCount": "123", "likeCount": "7", "commentCount": "4"},
    }


def make_client(handler: Any, **kwargs: Any) -> YouTubeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url=BASE_URL)
    return YouTubeClient(API_KEY, http_client=http, random_value=lambda: 0, **kwargs)


@pytest.mark.asyncio
async def test_search_request_construction_and_parsing() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=search_payload(), request=request)

    client = make_client(handler)
    page = await client.search_videos(
        "AI business",
        max_results=10,
        order="date",
        published_after=datetime(2026, 1, 1, tzinfo=UTC),
        page_token="page-2",
        region_code="US",
        relevance_language="en",
    )
    params = requests[0].url.params
    assert requests[0].url.path.endswith("/search")
    assert params["type"] == "video" and params["part"] == "snippet"
    assert params["q"] == "AI business" and params["maxResults"] == "10"
    assert params["publishedAfter"] == "2026-01-01T00:00:00Z"
    assert params["pageToken"] == "page-2" and params["key"] == API_KEY
    assert page.items[0].youtube_video_id == "video-1"
    assert page.items[0].published_at.tzinfo is not None
    assert page.page_info.total_results == 8


@pytest.mark.asyncio
async def test_search_returns_tokens_without_auto_pagination() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=search_payload(next_token="more", previous_token="back"))

    page = await make_client(handler).search_videos("query")
    assert page.next_page_token == "more" and page.prev_page_token == "back"
    assert calls == 1


@pytest.mark.asyncio
async def test_videos_are_batched_at_fifty_ids() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        identifiers = request.url.params["id"].split(",")
        batch_sizes.append(len(identifiers))
        return httpx.Response(200, json={"items": [video_item(item) for item in identifiers]})

    videos = await make_client(handler).get_videos([f"v-{index}" for index in range(51)])
    assert batch_sizes == [50, 1]
    assert len(videos) == 51


@pytest.mark.asyncio
async def test_video_statistics_duration_language_and_caption_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["part"] == "snippet,contentDetails,statistics"
        return httpx.Response(200, json={"items": [video_item()]})

    video = (await make_client(handler).get_videos(["video-1"]))[0]
    assert video.duration_seconds == 3723
    assert video.view_count == 123 and video.like_count == 7 and video.comment_count == 4
    assert video.language == "en" and video.has_captions is True


def test_iso_8601_duration_conversion() -> None:
    assert parse_duration_seconds("PT15M7S") == 907


@pytest.mark.asyncio
async def test_missing_video_statistics_remain_none() -> None:
    item = video_item()
    item.pop("statistics")
    client = make_client(lambda request: httpx.Response(200, json={"items": [item]}))
    video = (await client.get_videos(["video-1"]))[0]
    assert video.view_count is None and video.like_count is None and video.comment_count is None


@pytest.mark.asyncio
async def test_channel_parsing_and_hidden_subscribers() -> None:
    payload = {
        "items": [
            {
                "id": "c-1",
                "snippet": {"title": "Visible", "description": "", "country": "US"},
                "statistics": {"subscriberCount": "9", "videoCount": "2", "viewCount": "50"},
            },
            {
                "id": "c-2",
                "snippet": {"title": "Hidden", "description": ""},
                "statistics": {"hiddenSubscriberCount": True, "videoCount": "3"},
            },
        ]
    }
    channels = await make_client(lambda request: httpx.Response(200, json=payload)).get_channels(
        ["c-1", "c-2"]
    )
    assert channels[0].subscriber_count == 9 and channels[0].view_count == 50
    assert channels[1].subscriber_count is None


@pytest.mark.asyncio
async def test_comment_parsing_and_missing_stats() -> None:
    payload = {
        "items": [
            {
                "snippet": {
                    "totalReplyCount": 2,
                    "topLevelComment": {
                        "id": "comment-1",
                        "snippet": {
                            "videoId": "video-1",
                            "textOriginal": "A pain point",
                            "publishedAt": "2026-01-02T03:04:05Z",
                            "updatedAt": "2026-01-03T03:04:05Z",
                        },
                    },
                },
            }
        ],
        "nextPageToken": "next",
    }
    page = await make_client(lambda request: httpx.Response(200, json=payload)).get_comment_threads(
        "video-1", max_results=20, page_token="token", order="time"
    )
    assert page.items[0].youtube_comment_id == "comment-1"
    assert page.items[0].like_count is None and page.items[0].reply_count == 2
    assert page.next_page_token == "next"


def error_payload(reason: str, message: str = "Request failed") -> dict[str, Any]:
    return {"error": {"message": message, "errors": [{"reason": reason}]}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "reason", "exception"),
    [
        (400, "invalidParameter", YouTubeAPIError),
        (403, "keyInvalid", YouTubeAuthenticationError),
        (403, "quotaExceeded", YouTubeQuotaExceededError),
    ],
)
async def test_error_mapping(status: int, reason: str, exception: type[YouTubeAPIError]) -> None:
    client = make_client(
        lambda request: httpx.Response(status, json=error_payload(reason), request=request)
    )
    with pytest.raises(exception) as caught:
        await client.search_videos("query")
    assert caught.value.status_code == status and caught.value.reason == reason


@pytest.mark.asyncio
async def test_api_key_is_redacted_from_error() -> None:
    client = make_client(
        lambda request: httpx.Response(
            400, json=error_payload("badRequest", f"bad key {API_KEY}"), request=request
        )
    )
    with pytest.raises(YouTubeAPIError) as caught:
        await client.search_videos("query")
    assert API_KEY not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("statuses", [[429, 200], [500, 502, 200]])
async def test_transient_failures_retry_until_success(statuses: list[int]) -> None:
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        return httpx.Response(status, json=search_payload() if status == 200 else {})

    client = make_client(handler, sleep=sleep)
    assert (await client.search_videos("query")).items
    assert len(sleeps) in {1, 2}


@pytest.mark.asyncio
async def test_retry_after_is_respected() -> None:
    statuses = [429, 200]
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        return httpx.Response(status, headers={"Retry-After": "7"}, json=search_payload())

    await make_client(handler, sleep=sleep).search_videos("query")
    assert sleeps == [7.0]


@pytest.mark.asyncio
async def test_max_retry_exhaustion_maps_rate_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json=error_payload("rateLimitExceeded"), request=request)

    with pytest.raises(YouTubeRateLimitError):
        await make_client(handler, max_retries=3, sleep=lambda _: _no_sleep()).search_videos("q")
    assert calls == 3


async def _no_sleep() -> None:
    return None


@pytest.mark.asyncio
async def test_malformed_success_response_maps_validation_error() -> None:
    client = make_client(lambda request: httpx.Response(200, json={"items": [{}]}))
    with pytest.raises(YouTubeResponseValidationError):
        await client.search_videos("query")


def test_quota_cost_metadata_is_explicit() -> None:
    assert YouTubeQuotaCost.SEARCH_LIST == 100
    assert YouTubeQuotaCost.VIDEOS_LIST == 1
