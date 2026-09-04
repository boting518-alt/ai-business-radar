"""Explicit, constrained source-reference contracts."""

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from .common import SchemaModel
from .enums import AIExtractionSourceType


class VideoSourceRef(SchemaModel):
    source_type: Literal[AIExtractionSourceType.VIDEO] = AIExtractionSourceType.VIDEO
    source_id: UUID
    video_id: UUID

    @model_validator(mode="after")
    def source_ids_match(self) -> "VideoSourceRef":
        if self.source_id != self.video_id:
            raise ValueError("source_id must equal video_id")
        return self


class CommentSourceRef(SchemaModel):
    source_type: Literal[AIExtractionSourceType.COMMENT] = AIExtractionSourceType.COMMENT
    source_id: UUID
    comment_id: UUID

    @model_validator(mode="after")
    def source_ids_match(self) -> "CommentSourceRef":
        if self.source_id != self.comment_id:
            raise ValueError("source_id must equal comment_id")
        return self


class OpportunitySourceRef(SchemaModel):
    source_type: Literal[AIExtractionSourceType.OPPORTUNITY] = AIExtractionSourceType.OPPORTUNITY
    source_id: UUID
    opportunity_id: UUID

    @model_validator(mode="after")
    def source_ids_match(self) -> "OpportunitySourceRef":
        if self.source_id != self.opportunity_id:
            raise ValueError("source_id must equal opportunity_id")
        return self


AIExtractionSourceRef = VideoSourceRef | CommentSourceRef | OpportunitySourceRef
