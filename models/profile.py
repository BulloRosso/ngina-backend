# models/profile.py
from pydantic import BaseModel, UUID4, EmailStr
from datetime import date, datetime
from typing import List, Optional

class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    gender: str
    children: List[str] = []
    spoken_languages: List[str] = []
    profile_image_url: Optional[str]

class Profile(ProfileCreate):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

class Achievement(BaseModel):
    id: str
    type: str
    title: dict  # Multilingual
    description: dict  # Multilingual
    icon: str
    color: str
    required_count: int
    unlocked_at: Optional[datetime]

class AchievementProgress(BaseModel):
    profile_id: UUID4
    achievement_id: str
    current_count: int
    completed: bool
    unlocked_at: Optional[datetime]