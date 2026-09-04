from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class AIResponse:
    provider: str
    model: str
    parsed: BaseModel
    raw_output: dict[str, Any]
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class AIClient(Protocol):
    async def structured_generate(
        self,
        *,
        task_type: str,
        model: str,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
    ) -> AIResponse: ...
