"""Small shared validation primitives."""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

NormalizedConfidence = Annotated[Decimal, Field(ge=0, le=1)]
Score100 = Annotated[Decimal, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]

# Provider-facing JSON numbers. Keep these separate from Decimal-backed domain
# types because OpenAI Structured Outputs does not support Pydantic's Decimal
# string-fallback regular expression.
AIConfidence = Annotated[float, Field(ge=0.0, le=1.0)]
AIScore100 = Annotated[float, Field(ge=0.0, le=100.0)]
AINonNegativeNumber = Annotated[float, Field(ge=0.0)]


class SchemaModel(BaseModel):
    """Strict-boundary base model that rejects undocumented fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PriceRange(SchemaModel):
    min: NonNegativeDecimal | None = None
    max: NonNegativeDecimal | None = None
    currency: str | None = None
    period: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("price min must be less than or equal to max")
        if (self.min is not None or self.max is not None) and not self.currency:
            raise ValueError("currency is required when a price amount is present")


class AIPriceRange(SchemaModel):
    """Provider-facing price range; persistence converts amounts to Decimal."""

    min: AINonNegativeNumber | None = None
    max: AINonNegativeNumber | None = None
    currency: str | None = None
    period: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("price min must be less than or equal to max")
        if (self.min is not None or self.max is not None) and not self.currency:
            raise ValueError("currency is required when a price amount is present")


class RevenueClaim(SchemaModel):
    amount: NonNegativeDecimal | None = None
    currency: str | None = None
    period: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.amount is not None and not self.currency:
            raise ValueError("currency is required when a revenue amount is present")
