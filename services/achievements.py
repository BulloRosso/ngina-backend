# services/achievements.py
from typing import List
from uuid import UUID
from datetime import datetime
from models.profile import Achievement, AchievementProgress

class AchievementService:
    async def check_achievements(self, profile_id: UUID) -> List[Achievement]:
        try:
            stats = await self._get_profile_stats(profile_id)
            current_achievements = await self._get_current_achievements(profile_id)
            unlocked = []

            for achievement in self.ACHIEVEMENTS:
                if achievement.id not in current_achievements and \
                   await self._check_achievement_criteria(achievement, stats):
                    await self._unlock_achievement(profile_id, achievement.id)
                    unlocked.append(achievement)

            return unlocked
        except Exception as e:
            raise ValueError(f"Achievement check failed: {str(e)}")

    async def get_profile_achievements(
        self,
        profile_id: UUID,
        language: str = 'en'
    ) -> List[dict]:
        try:
            achievements = await self._get_all_achievements()
            progress = await self._get_achievement_progress(profile_id)

            return [
                {
                    **achievement.dict(),
                    'title': achievement.title[language],
                    'description': achievement.description[language],
                    'progress': progress.get(achievement.id, 0)
                }
                for achievement in achievements
            ]
        except Exception as e:
            raise ValueError(f"Failed to get achievements: {str(e)}")

    # Helper methods to be implemented
    async def _get_profile_stats(self, profile_id: UUID):
        pass

    async def _get_current_achievements(self, profile_id: UUID):
        pass

    async def _check_achievement_criteria(self, achievement: Achievement, stats: dict):
        pass

    async def _unlock_achievement(self, profile_id: UUID, achievement_id: str):
        pass