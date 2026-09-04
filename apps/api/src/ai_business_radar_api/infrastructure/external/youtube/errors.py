"""Safe internal YouTube client exceptions."""


class YouTubeAPIError(RuntimeError):
    def __init__(
        self, message: str, *, status_code: int | None = None, reason: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class YouTubeAuthenticationError(YouTubeAPIError):
    pass


class YouTubeQuotaExceededError(YouTubeAPIError):
    pass


class YouTubeRateLimitError(YouTubeAPIError):
    pass


class YouTubeNotFoundError(YouTubeAPIError):
    pass


class YouTubeResponseValidationError(YouTubeAPIError):
    pass
