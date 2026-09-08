from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ...infrastructure.auth import RequiredAdmin
from ...services.taxonomy import (
    ManualTaxonomyRequest,
    TaxonomyLabel,
    TaxonomyMappingResult,
    TaxonomyMappingService,
    TaxonomyNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["admin", "taxonomy"])


def service(request: Request) -> TaxonomyMappingService:
    return TaxonomyMappingService(request.app.state.database_session_factory)


@router.get("/taxonomy/{taxonomy_type}", response_model=list[TaxonomyLabel])
async def list_taxonomy(
    taxonomy_type: Literal["industry", "customer"],
    _: RequiredAdmin,
    mapping: Annotated[TaxonomyMappingService, Depends(service)],
    locale: Literal["en-US", "zh-CN"] = "en-US",
):
    return await mapping.nodes(taxonomy_type, locale)


async def mutate(
    entity_type: Literal["signal", "opportunity"],
    entity_id: UUID,
    body: ManualTaxonomyRequest,
    mapping: TaxonomyMappingService,
) -> TaxonomyMappingResult:
    try:
        if body.action == "clear":
            await mapping.clear_mapping(entity_type, entity_id, body.taxonomy_type)
            code, reason = None, "manual_clear"
        else:
            if body.taxonomy_code is None:
                raise HTTPException(422, "taxonomy_code is required for set")
            await mapping.set_mapping(
                entity_type, entity_id, body.taxonomy_type, body.taxonomy_code
            )
            code, reason = body.taxonomy_code, "manual_set"
    except TaxonomyNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    return TaxonomyMappingResult(
        entity_type=entity_type,
        entity_id=entity_id,
        taxonomy_type=body.taxonomy_type,
        original_text=None,
        normalized_text=None,
        taxonomy_code=code,
        status="mapped" if code else "unmapped",
        source="manual",
        confidence=None,
        reason=reason,
    )


@router.post("/signals/{entity_id}/taxonomy", response_model=TaxonomyMappingResult)
async def map_signal(
    entity_id: UUID,
    body: ManualTaxonomyRequest,
    _: RequiredAdmin,
    mapping: Annotated[TaxonomyMappingService, Depends(service)],
):
    return await mutate("signal", entity_id, body, mapping)


@router.post("/opportunities/{entity_id}/taxonomy", response_model=TaxonomyMappingResult)
async def map_opportunity(
    entity_id: UUID,
    body: ManualTaxonomyRequest,
    _: RequiredAdmin,
    mapping: Annotated[TaxonomyMappingService, Depends(service)],
):
    return await mutate("opportunity", entity_id, body, mapping)
