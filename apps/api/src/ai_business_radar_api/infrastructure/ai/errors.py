class AIError(RuntimeError):
    pass


class AIConfigurationError(AIError):
    pass


class AIProviderError(AIError):
    pass


class AIAuthenticationError(AIProviderError):
    pass


class AIRateLimitError(AIProviderError):
    pass


class AITransientError(AIProviderError):
    pass


class AIStructuredOutputError(AIProviderError):
    def __init__(self, message: str, *, raw_output: dict | None = None) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class PromptNotFoundError(AIError):
    pass
