import json
from typing import Any

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from ..client import AIResponse, OutputT
from ..errors import (
    AIAuthenticationError,
    AIProviderError,
    AIRateLimitError,
    AIStructuredOutputError,
    AITransientError,
)


class OpenAIClient:
    def __init__(self, api_key: str, *, max_retries: int = 2, client: AsyncOpenAI | None = None):
        self._api_key = api_key
        self._client = client or AsyncOpenAI(api_key=api_key, max_retries=max_retries)

    async def structured_generate(
        self,
        *,
        task_type: str,
        model: str,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
    ) -> AIResponse:
        try:
            response = await self._client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=json.dumps(input_data, ensure_ascii=False, sort_keys=True),
                text_format=output_model,
                store=False,
            )
        except openai.AuthenticationError as error:
            raise AIAuthenticationError("AI provider authentication failed") from error
        except openai.RateLimitError as error:
            raise AIRateLimitError("AI provider rate limit reached") from error
        except (openai.APIConnectionError, openai.APITimeoutError) as error:
            raise AITransientError("AI provider temporarily unavailable") from error
        except openai.APIError as error:
            raise AIProviderError("AI provider request failed") from error
        parsed: BaseModel | None = response.output_parsed
        raw = {"response_id": response.id, "output_text": response.output_text}
        if parsed is None:
            raise AIStructuredOutputError("AI response did not match the schema", raw_output=raw)
        usage = response.usage
        return AIResponse(
            provider="openai",
            model=model,
            parsed=parsed,
            raw_output=raw,
            provider_request_id=response.id,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
