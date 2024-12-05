# api/v1/achievements.py
from fastapi import APIRouter
from uuid import UUID
from services.achievements import AchievementService

router = APIRouter(prefix="/achievements", tags=["achievements"])

@router.get("/{profile_id}")
async def get_achievements(profile_id: UUID, language: str = 'en'):
    service = AchievementService()
    return await service.get_profile_achievements(profile_id, language)

@router.post("/check")
async def check_achievements(profile_id: UUID):
    service = AchievementService()
    unlocked = await service.check_achievements(profile_id)
    return {"unlocked_achievements": unlocked}
