from fastapi import APIRouter
from .interviews import router as interviews_router
from .memories import router as memories_router
from .achievements import router as achievements_router

router = APIRouter(prefix="/v1")
router.include_router(interviews_router)
router.include_router(memories_router)
router.include_router(achievements_router)