"""Identity and RAW persistence mappings."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    auth_user_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    role: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SearchQuery(Base):
    __tablename__ = "search_queries"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    query: Mapped[str] = mapped_column(Text)
    query_group: Mapped[str]
    language: Mapped[str | None]
    region: Mapped[str | None]
    enabled: Mapped[bool] = mapped_column(Boolean)
    priority: Mapped[Decimal] = mapped_column(Numeric)
    discovery_mode: Mapped[str]
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("discovery_topics.id"))
    max_videos: Mapped[int | None] = mapped_column(Integer)
    max_pages: Mapped[int | None] = mapped_column(Integer)
    max_comments_per_video: Mapped[int | None] = mapped_column(Integer)
    schedule_override: Mapped[str | None]


class DiscoveryTopic(Base):
    __tablename__ = "discovery_topics"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str]
    default_schedule: Mapped[str]
    default_max_videos: Mapped[int] = mapped_column(Integer)
    default_max_pages: Mapped[int] = mapped_column(Integer)
    default_max_comments_per_video: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("user_profiles.id"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DiscoveryTopicRun(Base):
    __tablename__ = "discovery_topic_runs"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[UUID] = mapped_column(ForeignKey("discovery_topics.id"))
    trigger_type: Mapped[str]
    status: Mapped[str]
    requested_query_count: Mapped[int] = mapped_column(Integer)
    queued_query_count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intelligence_status: Mapped[str] = mapped_column(server_default=text("'not_started'"))
    intelligence_metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    intelligence_error_summary: Mapped[str | None] = mapped_column(Text)
    intelligence_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intelligence_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[str]
    run_type: Mapped[str]
    status: Mapped[str]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_query_id: Mapped[UUID | None] = mapped_column(ForeignKey("search_queries.id"))
    items_discovered: Mapped[int] = mapped_column(Integer)
    items_processed: Mapped[int] = mapped_column(Integer)
    items_failed: Mapped[int] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discovery_topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("discovery_topics.id"))
    trigger_type: Mapped[str | None]
    worker_message_id: Mapped[str | None] = mapped_column(Text)
    topic_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("discovery_topic_runs.id"))


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    youtube_channel_id: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None]
    subscriber_count: Mapped[int | None] = mapped_column(BigInteger)
    video_count: Mapped[int | None] = mapped_column(BigInteger)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    channel_type: Mapped[str | None]
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    youtube_video_id: Mapped[str] = mapped_column(unique=True)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None]
    category_id: Mapped[str | None]
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    current_view_count: Mapped[int | None] = mapped_column(BigInteger)
    current_like_count: Mapped[int | None] = mapped_column(BigInteger)
    current_comment_count: Mapped[int | None] = mapped_column(BigInteger)
    has_captions: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processing_status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VideoSnapshot(Base):
    __tablename__ = "video_snapshots"
    __table_args__ = (UniqueConstraint("video_id", "captured_at"),)
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    video_id: Mapped[UUID] = mapped_column(ForeignKey("videos.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    youtube_comment_id: Mapped[str] = mapped_column(unique=True)
    video_id: Mapped[UUID] = mapped_column(ForeignKey("videos.id"))
    text: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    like_count: Mapped[int | None] = mapped_column(Integer)
    reply_count: Mapped[int | None] = mapped_column(Integer)
    author_hash: Mapped[str | None]
    is_question: Mapped[bool | None] = mapped_column(Boolean)
    language: Mapped[str | None]
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class YouTubeDiscoveryItem(Base):
    __tablename__ = "youtube_discovery_items"
    __table_args__ = (UniqueConstraint("collection_run_id", "youtube_video_id"),)
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    collection_run_id: Mapped[UUID] = mapped_column(ForeignKey("collection_runs.id"))
    search_query_id: Mapped[UUID] = mapped_column(ForeignKey("search_queries.id"))
    youtube_video_id: Mapped[str]
    youtube_channel_id: Mapped[str]
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel_title: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processing_status: Mapped[str]
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_video_id: Mapped[UUID | None] = mapped_column(ForeignKey("videos.id"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
