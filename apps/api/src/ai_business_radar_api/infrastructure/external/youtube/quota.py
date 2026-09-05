"""Published YouTube Data API quota-unit estimates."""

from enum import IntEnum


class YouTubeQuotaCost(IntEnum):
    # Since June 2026, search.list uses a dedicated 100-calls/day bucket and
    # each request costs one unit in that bucket.
    SEARCH_LIST = 1
    VIDEOS_LIST = 1
    CHANNELS_LIST = 1
    COMMENT_THREADS_LIST = 1
