"""Published YouTube Data API quota-unit estimates."""

from enum import IntEnum


class YouTubeQuotaCost(IntEnum):
    SEARCH_LIST = 100
    VIDEOS_LIST = 1
    CHANNELS_LIST = 1
    COMMENT_THREADS_LIST = 1
