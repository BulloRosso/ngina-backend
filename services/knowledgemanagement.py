# services/knowledgemanagement.py
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging
from uuid import UUID
from models.memory import (
    Category, 
    Memory, 
    Location, 
    MemoryCreate, 
    Person,
    Emotion
)
from services.memory import MemoryService

logger = logging.getLogger(__name__)

class MemoryClassification(BaseModel):
    """Model for classified memory information"""
    is_memory: bool
    rewritten_text: str
    category: Optional[str]
    location: Optional[str]
    timestamp: str  # ISO format date string

class KnowledgeManagement:
    """Class for managing knowledge management"""
    def __init__(self):
        self.memory_service = MemoryService()
    
    @staticmethod
    async def analyze_response(response_text: str, client, language: str = "en") -> MemoryClassification:
        """Analyze user response to classify and enhance memory content"""
        try:
            # Update the prompt to handle unknown dates and locations better
            prompt = f"""Analyze the following text and classify it as a memory or not. 
            If it is a memory, rewrite it in complete sentences using a friendly and optimistic tone, 
            in first person view. Also extract the category, location, and timestamp.
            If the exact date is unknown, please estimate the month and year based on context clues
            or use the current date if no time information is available.

            IMPORTANT: Keep the response in the original language ({language}).

            Text: {response_text}

            Return result as JSON with the following format:
            {{
                "is_memory": true/false,
                "rewritten_text": "rewritten memory in {language}",
                "category": "one of: childhood, career, travel, relationships, hobbies, pets",
                "location": "where it happened or 'Unknown' if not mentioned",
                "timestamp": "YYYY-MM-DD (if unknown, use current date)"
            }}
            """

            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a memory analysis assistant that responds in {language}. Keep the rewritten text in the original language."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = response.choices[0].message.content
            classification = MemoryClassification.parse_raw(result)

            # Set default current date if timestamp is invalid
            if classification.timestamp in ["unbekannt", "unknown", ""]:
                classification.timestamp = datetime.now().strftime("%Y-%m-%d")

            classification.timestamp = classification.timestamp.replace("-XX", "-01")
            
            logger.info(f"Memory classification complete: {classification}")
            return classification

        except Exception as e:
            logger.error(f"Error analyzing response: {str(e)}")
            raise

    async def store_memory(self, profile_id: UUID, session_id: UUID, classification: MemoryClassification) -> Optional[Memory]:
        """
        Store classified memory in both Supabase and Neo4j (future implementation)
        """
        try:
            if not classification.is_memory:
                logger.debug("Text classified as non-memory, skipping storage")
                return None
            
            # Parse timestamp or use current date if invalid
            try:
                timestamp = datetime.fromisoformat(classification.timestamp)
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp '{classification.timestamp}', using current date")
                timestamp = datetime.now()
                
            # Prepare memory data
            memory_data = {
                "category": classification.category or Category.CHILDHOOD.value,
                "description": classification.rewritten_text,
                "time_period": datetime.fromisoformat(classification.timestamp),
                "location": {
                    "name": classification.location if classification.location != "unbekannt" else "Unknown",
                    "city": None,
                    "country": None,
                    "description": None
                } if classification.location else None,
                "people": [],
                "emotions": [],
                "image_urls": [],
                "audio_url": None
            }

            # Store in Supabase
            stored_memory = await MemoryService.create_memory(
                MemoryCreate(**memory_data),
                profile_id,
                session_id
            )

            # TODO: Store in Neo4j knowledge graph
            # This will be implemented later to create nodes and relationships
            # in the graph database based on the memory content

            logger.info(f"Memory stored successfully")
            return stored_memory

        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}")
            raise