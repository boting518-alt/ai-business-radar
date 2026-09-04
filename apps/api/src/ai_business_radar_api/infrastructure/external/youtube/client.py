"""Async official YouTube Data API v3 client."""

import asyncio
import random
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx

from .errors import (
    YouTubeAPIError,
    YouTubeAuthenticationError,
    YouTubeNotFoundError,
    YouTubeQuotaExceededError,
    YouTubeRateLimitError,
)
from .models import YouTubeChannel, YouTubeCommentPage, YouTubeSearchPage, YouTubeVideo
from .parsing import parse_channels, parse_comment_page, parse_search_page, parse_videos

Sleep = Callable[[float], Awaitable[None]]
SearchOrder = Literal["date", "relevance", "viewCount"]
CommentOrder = Literal["time", "relevance"]
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
AUTH_REASONS = {"keyInvalid", "ipRefererBlocked", "forbidden", "accessNotConfigured"}
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg"}


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://www.googleapis.com/youtube/v3/",
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if not api_key:
            raise ValueError("YouTube API key is required")
        if max_retries < 1:
            raise ValueError("max_retries must allow at least one attempt")
        self._api_key = api_key
        self._max_attempts = max_retries
        self._sleep = sleep
        self._random_value = random_value
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/", timeout=timeout_seconds
        )

    async def __aenter__(self) -> "YouTubeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def search_videos(
        self,
        query: str,
        *,
        max_results: int = 25,
        order: SearchOrder = "relevance",
        published_after: datetime | None = None,
        page_token: str | None = None,
        region_code: str | None = None,
        relevance_language: str | None = None,
    ) -> YouTubeSearchPage:
        self._validate_page_size(max_results, maximum=50)
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": max_results,
            "order": order,
        }
        if published_after is not None:
            if published_after.tzinfo is None:
                raise ValueError("published_after must be timezone-aware")
            params["publishedAfter"] = (
                published_after.astimezone(UTC).isoformat().replace("+00:00", "Z")
            )
        self._add_optional(
            params,
            pageToken=page_token,
            regionCode=region_code,
            relevanceLanguage=relevance_language,
        )
        return parse_search_page(await self._request("search", params))

    async def get_videos(self, video_ids: Sequence[str]) -> list[YouTubeVideo]:
        videos: list[YouTubeVideo] = []
        for identifiers in self._batches(video_ids, 50):
            payload = await self._request(
                "videos",
                {"part": "snippet,contentDetails,statistics", "id": ",".join(identifiers)},
            )
            videos.extend(parse_videos(payload))
        return videos

    async def get_channels(self, channel_ids: Sequence[str]) -> list[YouTubeChannel]:
        channels: list[YouTubeChannel] = []
        for identifiers in self._batches(channel_ids, 50):
            payload = await self._request(
                "channels", {"part": "snippet,statistics", "id": ",".join(identifiers)}
            )
            channels.extend(parse_channels(payload))
        return channels

    async def get_comment_threads(
        self,
        video_id: str,
        *,
        max_results: int = 100,
        page_token: str | None = None,
        order: CommentOrder = "relevance",
    ) -> YouTubeCommentPage:
        self._validate_page_size(max_results, maximum=100)
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": max_results,
            "order": order,
            "textFormat": "plainText",
        }
        self._add_optional(params, pageToken=page_token)
        return parse_comment_page(await self._request("commentThreads", params))

    async def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {**params, "key": self._api_key}
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._http.get(endpoint, params=request_params)
            except httpx.TransportError as error:
                if attempt == self._max_attempts:
                    raise YouTubeAPIError("YouTube request failed after retries") from error
                await self._sleep(self._backoff(attempt, None))
                continue
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_attempts:
                await self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.is_error:
                raise self._map_error(response)
            try:
                payload = response.json()
            except ValueError as error:
                from .errors import YouTubeResponseValidationError

                raise YouTubeResponseValidationError(
                    "YouTube returned a non-JSON response", status_code=response.status_code
                ) from error
            if not isinstance(payload, dict):
                from .errors import YouTubeResponseValidationError

                raise YouTubeResponseValidationError("YouTube returned an invalid response")
            return payload
        raise AssertionError("retry loop did not return or raise")

    def _map_error(self, response: httpx.Response) -> YouTubeAPIError:
        reason, message = self._safe_error_details(response)
        message = message.replace(self._api_key, "[redacted]")
        kwargs = {"status_code": response.status_code, "reason": reason}
        if reason in QUOTA_REASONS:
            return YouTubeQuotaExceededError(message, **kwargs)
        if response.status_code == 429 or reason == "rateLimitExceeded":
            return YouTubeRateLimitError(message, **kwargs)
        if response.status_code in {401, 403} or reason in AUTH_REASONS:
            return YouTubeAuthenticationError(message, **kwargs)
        if response.status_code == 404:
            return YouTubeNotFoundError(message, **kwargs)
        return YouTubeAPIError(message, **kwargs)

    @staticmethod
    def _safe_error_details(response: httpx.Response) -> tuple[str | None, str]:
        reason = None
        message = f"YouTube API request failed with status {response.status_code}"
        try:
            error = response.json().get("error", {})
            if isinstance(error.get("message"), str):
                message = error["message"]
            details = error.get("errors", [])
            if details and isinstance(details[0], dict):
                reason = details[0].get("reason")
        except (AttributeError, TypeError, ValueError):
            pass
        return reason, message

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    return max(
                        0.0,
                        (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds(),
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
        return (2 ** (attempt - 1)) + self._random_value()

    @staticmethod
    def _validate_page_size(value: int, *, maximum: int) -> None:
        if not 1 <= value <= maximum:
            raise ValueError(f"max_results must be between 1 and {maximum}")

    @staticmethod
    def _batches(values: Sequence[str], size: int) -> list[Sequence[str]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    @staticmethod
    def _add_optional(params: dict[str, Any], **values: Any) -> None:
        params.update({key: value for key, value in values.items() if value is not None})
