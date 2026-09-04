"""Canonical frozen taxonomy values for v0.1."""

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class DiscoveryMode(StrEnum):
    DISCOVERY = "discovery"
    MONITORING = "monitoring"


class QueryGroup(StrEnum):
    TECHNOLOGY = "technology"
    BUSINESS = "business"
    REVENUE = "revenue"
    PAIN = "pain"
    INDUSTRY = "industry"
    DISCOVERY = "discovery"


class CollectionSourceType(StrEnum):
    YOUTUBE = "youtube"


class CollectionRunType(StrEnum):
    DISCOVERY = "discovery"
    CHANNEL_MONITOR = "channel_monitor"
    VIDEO_SNAPSHOT = "video_snapshot"
    COMMENT_COLLECTION = "comment_collection"


class CollectionRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChannelType(StrEnum):
    FOUNDER = "founder"
    BUSINESS_MEDIA = "business_media"
    AI_EDUCATOR = "ai_educator"
    VC = "vc"
    CONSULTANT = "consultant"
    VENDOR = "vendor"
    NEWS = "news"
    UNKNOWN = "unknown"


class VideoProcessingStatus(StrEnum):
    NEW = "new"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    REVIEW = "review"
    IGNORED = "ignored"
    FAILED = "failed"


class AIExtractionSourceType(StrEnum):
    VIDEO = "video"
    COMMENT = "comment"
    OPPORTUNITY = "opportunity"


class AIExtractionTaskType(StrEnum):
    RELEVANCE_FILTER = "relevance_filter"
    SIGNAL_EXTRACTOR = "signal_extractor"
    COMMENT_PAIN_MINER = "comment_pain_miner"
    OPPORTUNITY_NORMALIZER = "opportunity_normalizer"
    HYPE_DETECTOR = "hype_detector"


class AIExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID_OUTPUT = "invalid_output"


class SignalSourceType(StrEnum):
    VIDEO = "video"
    COMMENT = "comment"


class SignalType(StrEnum):
    PAIN = "pain"
    DEMAND = "demand"
    PURCHASE_INTENT = "purchase_intent"
    REVENUE = "revenue"
    PRICING = "pricing"
    CUSTOMER = "customer"
    PRODUCT_LAUNCH = "product_launch"
    GROWTH = "growth"
    COMPETITION = "competition"
    DISTRIBUTION = "distribution"
    WORKFLOW = "workflow"
    TECHNOLOGY = "technology"
    MARKET_CHANGE = "market_change"
    COMPLAINT = "complaint"
    FEATURE_REQUEST = "feature_request"
    ADOPTION = "adoption"


class ClaimStatus(StrEnum):
    FACT = "fact"
    CREATOR_CLAIM = "creator_claim"
    INFERRED = "inferred"
    OPINION = "opinion"
    SPECULATION = "speculation"
    UNKNOWN = "unknown"


class SignalStatus(StrEnum):
    ACTIVE = "active"
    REVIEW = "review"
    IGNORED = "ignored"
    REJECTED = "rejected"


class MarketStage(StrEnum):
    UNKNOWN = "unknown"
    EMERGING = "emerging"
    ACCELERATING = "accelerating"
    VALIDATED = "validated"
    CROWDED = "crowded"
    MATURE = "mature"
    DECLINING = "declining"


class OpportunityStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    REVIEW = "review"
    MERGED = "merged"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class OpportunitySignalRelationshipType(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    CONTEXT = "context"
    CANDIDATE_MATCH = "candidate_match"


class EvidenceSourceType(StrEnum):
    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_COMMENT = "youtube_comment"
    MANUAL = "manual"


class EvidenceType(StrEnum):
    PAIN = "pain"
    DEMAND = "demand"
    PRICING = "pricing"
    REVENUE = "revenue"
    COMPETITION = "competition"
    ADOPTION = "adoption"
    DISTRIBUTION = "distribution"
    GROWTH = "growth"
    MARKET_CONTEXT = "market_context"


class TrendWindowType(StrEnum):
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"


class ReviewType(StrEnum):
    SIGNAL_VALIDATION = "signal_validation"
    OPPORTUNITY_MATCH = "opportunity_match"
    OPPORTUNITY_MERGE = "opportunity_merge"
    OPPORTUNITY_CREATION = "opportunity_creation"
    HYPE_REVIEW = "hype_review"
    QUALITY_REVIEW = "quality_review"


class ReviewTargetType(StrEnum):
    SIGNAL = "signal"
    OPPORTUNITY = "opportunity"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    MERGE = "merge"
    CREATE_NEW = "create_new"
    REJECT = "reject"
    IGNORE = "ignore"
    DEFER = "defer"


class OpportunityNormalizationAction(StrEnum):
    MATCH = "MATCH"
    CREATE = "CREATE"
    REVIEW = "REVIEW"


class HypeClassification(StrEnum):
    CONTENT_DRIVEN = "content_driven"
    MIXED = "mixed"
    DEMAND_DRIVEN = "demand_driven"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
