# models/memory.py
from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum

class Category(str, Enum):
    CHILDHOOD = "childhood"
    CAREER = "career"
    TRAVEL = "travel"
    RELATIONSHIPS = "relationships"
    HOBBIES = "hobbies"
    PETS = "pets"

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
    description: str
    time_period: datetime
    location: Optional[Location]
    people: List[Person] = []
    emotions: List[Emotion] = []
    image_urls: List[str] = []
    audio_url: Optional[str]

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
    audio_url: Optional[str]
    emotions_detected: Optional[List[Emotion]]

class InterviewQuestion(BaseModel):
    text: str
    context: Optional[str]
    suggested_topics: List[str] = []
    requires_media: bool = False