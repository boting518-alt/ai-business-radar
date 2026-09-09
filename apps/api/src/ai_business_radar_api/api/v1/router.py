"""Version 1 route composition."""

from fastapi import APIRouter

from .admin import router as admin_router
from .ai_comment_pain import router as ai_comment_pain_router
from .ai_opportunities import router as ai_opportunities_router
from .ai_relevance import router as ai_relevance_router
from .ai_signals import router as ai_signals_router
from .auth import router as auth_router
from .candidates import router as candidates_router
from .consolidation import router as consolidation_router
from .discovery_operations import router as discovery_operations_router
from .health import router as health_router
from .localization import router as localization_router
from .opportunity_activation import router as opportunity_activation_router
from .radar import router as radar_router
from .reviews import router as reviews_router
from .scoring import router as scoring_router
from .taxonomy import router as taxonomy_router
from .trends import router as trends_router
from .watchlist import router as watchlist_router
from .youtube_discovery import router as youtube_discovery_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(discovery_operations_router)
router.include_router(youtube_discovery_router)
router.include_router(ai_relevance_router)
router.include_router(ai_comment_pain_router)
router.include_router(ai_opportunities_router)
router.include_router(ai_signals_router)
router.include_router(localization_router)
router.include_router(trends_router)
router.include_router(scoring_router)
router.include_router(candidates_router)
router.include_router(consolidation_router)
router.include_router(opportunity_activation_router)
router.include_router(reviews_router)
router.include_router(radar_router)
router.include_router(watchlist_router)
router.include_router(taxonomy_router)
