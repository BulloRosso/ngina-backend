# models/memory.py
from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
from uuid import UUID, uuid4
from pydantic.json import timedelta_isoformat

class Category(str, Enum):
    CHILDHOOD = "childhood"
    CAREER = "career"
    TRAVEL = "travel"
    RELATIONSHIPS = "relationships"
    HOBBIES = "hobbies"
    PETS = "pets"

    @classmethod
    def _missing_(cls, value):
        """Handle case when enum value has 'Category.' prefix"""
        if isinstance(value, str):
            # Remove 'Category.' prefix if it exists
            clean_value = value.replace('Category.', '').lower()
            for member in cls:
                if member.value.lower() == clean_value:
                    return member
        return None

class Person(BaseModel):
    name: str
    relation: str
    age_at_time: Optional[int]

class Location(BaseModel):
    name: str
    city: Optional[str]
    country: Optional[str]
    description: Optional[str]

class Emotion(BaseModel):
    type: str
    intensity: float
    description: Optional[str]

class MemoryCreate(BaseModel):
    category: Category
    original_user_input: Optional[str] = None
    description: str
    caption: Optional[str] = None  
    original_description: Optional[str] = None
    time_period: datetime
    location: Optional[Location]
    people: List[Person] = []
    emotions: List[Emotion] = []
    image_urls: List[str] = []
    audio_url: Optional[str] = None

class MemoryUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None  
    original_description: Optional[str] = None
    time_period: Optional[str] = None  # Keep as string instead of datetime
    location: Optional[dict] = None
    people: Optional[List[dict]] = None
    emotions: Optional[List[dict]] = None
    image_urls: Optional[List[str]] = None
    audio_url: Optional[str] = None

    model_config = {
        'json_encoders': {
            datetime: lambda v: v.isoformat()
        },
        'populate_by_name': True
    }

    @classmethod
    def validate_time_period(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
class Memory(MemoryCreate):
    id: UUID4
    profile_id: UUID4
    session_id: UUID4
    created_at: datetime
    updated_at: datetime
    sentiment_analysis: Optional[Dict]

class InterviewResponse(BaseModel):
    text: str
    language: str
    memory_id: Optional[str] = None
    session_id: Optional[UUID] = None  
    user_id: UUID

class InterviewQuestion(BaseModel):
    text: str
    context: Optional[str]
    suggested_topics: List[str] = []
    requires_media: bool = False