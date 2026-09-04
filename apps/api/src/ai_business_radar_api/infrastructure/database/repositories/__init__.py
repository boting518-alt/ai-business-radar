"""Small, domain-oriented repositories sharing a caller-owned session."""

from .channels import ChannelRepository
from .comments import CommentRepository
from .opportunities import OpportunityRepository
from .reviews import ReviewTaskRepository
from .signals import SignalRepository
from .videos import VideoRepository
from .watchlists import WatchlistRepository

__all__ = [
    "ChannelRepository",
    "CommentRepository",
    "OpportunityRepository",
    "ReviewTaskRepository",
    "SignalRepository",
    "VideoRepository",
    "WatchlistRepository",
]
