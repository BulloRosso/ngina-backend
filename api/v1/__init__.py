# api/v1/__init__.py
from fastapi import APIRouter
from .interviews import router as interviews_router
from .memories import router as memories_router
from .achievements import router as achievements_router
from .profiles import router as profiles_router
from .auth  import router as auth_router
from .chat  import router as chat_router
from .invitations import router as invitations_router

router = APIRouter(prefix="/v1")
router.include_router(interviews_router)
router.include_router(memories_router)
router.include_router(achievements_router)
router.include_router(profiles_router)
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(invitations_router)