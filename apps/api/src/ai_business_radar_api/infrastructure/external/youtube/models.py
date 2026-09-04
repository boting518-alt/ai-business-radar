"""YouTube infrastructure DTOs, separate from shared domain schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class YouTubeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YouTubePageInfo(YouTubeDTO):
    total_results: int | None = None
    results_per_page: int | None = None


class YouTubeSearchItem(YouTubeDTO):
    youtube_video_id: str
    youtube_channel_id: str
    title: str
    description: str
    published_at: datetime
    channel_title: str
    thumbnail_url: str | None = None


class YouTubeSearchPage(YouTubeDTO):
    items: list[YouTubeSearchItem]
    next_page_token: str | None = None
    prev_page_token: str | None = None
    page_info: YouTubePageInfo | None = None


class YouTubeVideo(YouTubeDTO):
    youtube_video_id: str
    youtube_channel_id: str
    title: str
    description: str
    published_at: datetime
    category_id: str | None = None
    language: str | None = None
    duration_seconds: int
    thumbnail_url: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    has_captions: bool | None = None


class YouTubeChannel(YouTubeDTO):
    youtube_channel_id: str
    name: str
    description: str
    country: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None


class YouTubeComment(YouTubeDTO):
    youtube_comment_id: str
    video_id: str
    text: str
    published_at: datetime
    updated_at: datetime | None = None
    like_count: int | None = None
    reply_count: int | None = None


class YouTubeCommentPage(YouTubeDTO):
    items: list[YouTubeComment]
    next_page_token: str | None = None
