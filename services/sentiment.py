# services/sentiment.py
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from models.memory import InterviewResponse, InterviewQuestion, MemoryCreate, Location, Category 
import openai
import os
from typing import Dict, Any, Optional
from supabase import create_client, Client
import logging
from services.knowledgemanagement import KnowledgeManagement, MemoryClassification
from services.memory import MemoryService 
import asyncio
import random

logger = logging.getLogger(__name__)

class SessionStatus:
    ACTIVE = "active"
    COMPLETED = "completed"
    
class EmpatheticInterviewer:
    def __init__(self):
        self.openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.knowledge_manager = KnowledgeManagement()

    async def get_initial_question(self, profile_id: UUID, language: str = "en") -> str:
        """
        Generate the initial question for an interview in the specified language.
        """
        try:
            # Fetch profile data
            profile_result = self.supabase.table("profiles")\
                .select("*")\
                .eq("id", str(profile_id))\
                .execute()

            if not profile_result.data:
                raise Exception("Profile not found")

            profile = profile_result.data[0]
            backstory = profile.get("metadata", {}).get("backstory", "")
            name = f"{profile['first_name']} {profile['last_name']}"

            # Create system prompt
            system_prompt = f"""You are an empathetic interviewer helping {name} preserve their memories.

            Context about {name}:
            {backstory if backstory else "No previous context available."}

            Generate a warm, inviting opening question in {language} that:
            1. Makes the person feel comfortable sharing memories
            2. References their background if available
            3. Is open-ended but specific enough to trigger memories
            4. Uses appropriate cultural references based on their background

            The entire response should be in {language} language only."""

            # Generate question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Generate an opening question for {name}'s memory preservation interview."
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )

            initial_question = response.choices[0].message.content
            return initial_question

        except Exception as e:
            logger.error(f"Error generating initial question: {str(e)}")
            # Return default messages based on language
            default_messages = {
                "en": "Could you share a meaningful memory from your life?",
                "de": "Können Sie eine bedeutungsvolle Erinnerung aus Ihrem Leben teilen?"
                # Add more languages as needed
            }
            return default_messages.get(language, default_messages["en"])
            
    async def process_interview_response(
        self,
        user_id: UUID,
        profile_id: UUID,
        session_id: UUID,
        response_text: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process a response from the interviewee and generate the next question.
        """
        try:

            # Second, fetch the profile
            profile_basics = self.supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()

            if not profile_basics.data:
                raise Exception("Profile not found")

            profile_data = profile_basics.data[0]
            metadata = profile_data.get('metadata', {})

            # Get narrative settings from metadata
            narrator_perspective = metadata.get('narrator_perspective', 'ego')
            narrator_style = metadata.get('narrator_style', 'neutral')
            narrator_verbosity = metadata.get('narrator_verbosity', 'normal')

            logger.debug(f"Using profile settings - perspective: {narrator_perspective}, style: {narrator_style}, verbosity: {narrator_verbosity}")

            # Analyze if the response is a memory and classify it with profile settings
            classification = await KnowledgeManagement.analyze_response(
                response_text=response_text, 
                client=self.openai_client,
                profile_data=profile_data, 
                language=language,
                narrator_perspective=narrator_perspective,
                narrator_style=narrator_style,
                narrator_verbosity=narrator_verbosity
            )

            logger.info("------- Analyzed response -------")
            logger.info(f"is_memory={classification.is_memory} "
                      f"category='{classification.category}' "
                      f"location='{classification.location}' "
                      f"timestamp='{classification.timestamp}'")

            # Initialize memory_id as None
            memory_id = None
            
            # If it's a memory, store it
            if classification.is_memory:
                logger.info(f"rewrittenText='{classification.rewritten_text}'")
                logger.info(f"caption='{classification.caption}'")  
                logger.info(f"narrator_perspective='{narrator_perspective}'")
                
                # Create memory with original description and caption
                memory_data = MemoryCreate(
                    category=classification.category,
                    description=classification.rewritten_text,
                    original_description=response_text,  # NEW
                    caption=classification.caption,  # NEW
                    time_period=datetime.fromisoformat(classification.timestamp),
                    location=Location(
                        name=classification.location if classification.location != "unbekannt" else "Unknown",
                        city=None,
                        country=None,
                        description=None
                    ) if classification.location else None
                )
                
                memory_id = await MemoryService.create_memory(
                    memory_data,
                    profile_id,
                    session_id
                )

                # Asynchronously update the knowledge graph
                asyncio.create_task(self.knowledge_manager.append_to_rag(
                    classification.rewritten_text, 
                    str(profile_id), 
                    str(memory_id), 
                    classification.category, 
                    classification.location
                ))

                # Generate follow-up question based on the processed response
                next_question = await self.generate_next_question(
                    profile_id, 
                    session_id,
                    language
                )
            else:
                # Use RAG for non-memory responses
                logger.info("Using RAG for non-memory response")
                next_question = await self.knowledge_manager.query_with_rag(response_text, str(profile_id))
            
            # Return default sentiment values instead of analyzing
            default_sentiment = {
                "joy": 0.5,
                "sadness": 0.0,
                "nostalgia": 0.5,
                "intensity": 0.5
            }

            return {
                "sentiment": default_sentiment,
                "follow_up": next_question,
                "is_memory": classification.is_memory,
                "memory_id": memory_id
            }

        except Exception as e:
            print(f"Error processing interview response: {str(e)}")
            return {
                "sentiment": {"joy": 0.5, "nostalgia": 0.5},
                "follow_up": "Can you tell me more about that?",
                "is_memory": False,
                "memory_id": None
            }

    async def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze the emotional content of the response.
        """
        try:
            response = self.openai_client.chat.completions.create(  # Remove await
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the emotional content of this memory and return scores from 0 to 1 for: joy, sadness, nostalgia, and intensity."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=100
            )

            # Parse the response to extract sentiment scores
            sentiment = {
                "joy": 0.5,
                "sadness": 0.0,
                "nostalgia": 0.5,
                "intensity": 0.5
            }

            return sentiment

        except Exception as e:
            print(f"Error analyzing sentiment: {str(e)}")
            return {
                "joy": 0.5,
                "sadness": 0.0,
                "nostalgia": 0.5,
                "intensity": 0.5
            }

    async def generate_next_question(self, profile_id: UUID, session_id: UUID, language: str = "en") -> str:
        """Generate the next question based on previous responses."""
        try:
            # Get previous responses...
            previous_responses = self.supabase.table("memories").select(
                "description"
            ).eq(
                "session_id", str(session_id)
            ).order(
                "created_at", desc=True
            ).limit(3).execute()

            context = ""
            if previous_responses.data:
                context = "Previous responses: " + " ".join(
                    [r["description"] for r in previous_responses.data]
                )

            # Generate follow-up question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an empathetic interviewer helping people preserve their 
                        memories. Generate a follow-up question that encourages deeper sharing and 
                        reflection. Focus on details, emotions, and sensory experiences.
                        Respond in {language} language only."""
                    },
                    {
                        "role": "user",
                        "content": f"Given this context: {context}\nGenerate an engaging follow-up question."
                    }
                ],
                max_tokens=100
            )

            next_question = response.choices[0].message.content
            return next_question

        except Exception as e:
            logger.error(f"Error generating next question: {str(e)}")
            # Return default messages in the correct language
            default_messages = {
                "en": "What other memories would you like to share today?",
                "de": "Welche anderen Erinnerungen möchten Sie heute teilen?"
                # Add more languages as needed
            }
            return default_messages.get(language, default_messages["en"])

    async def get_or_create_session(self, profile_id: UUID) -> dict:
        """
        Gets an existing active session or creates a new one.
        Also handles cleanup of stale sessions.
        """
        try:
            # First, get any active session for this profile
            result = self.supabase.table("interview_sessions")\
                .select("*")\
                .eq("profile_id", str(profile_id))\
                .eq("status", SessionStatus.ACTIVE)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()

            # If an active session exists, check if it's still valid
            if result.data:
                session = result.data[0]
                if await self.validate_session(session):
                    logger.info(f"Reusing existing session {session['id']} for profile {profile_id}")
                    return session

            # If we get here, either no active session exists or it was invalid
            # First clean up any stale sessions
            await self.close_stale_sessions(profile_id)

            # Create new session
            session_data = {
                "id": str(uuid4()),
                "profile_id": str(profile_id),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "status": SessionStatus.ACTIVE,
                "last_question": None
            }

            result = self.supabase.table("interview_sessions").insert(session_data).execute()
            logger.info(f"Created new session {session_data['id']} for profile {profile_id}")

            return result.data[0]

        except Exception as e:
            logger.error(f"Error in get_or_create_session: {str(e)}")
            raise
    
    async def validate_session(self, session: dict) -> bool:
        """
        Validates if a session is active and can be used.
        """
        try:
            if session['status'] != SessionStatus.ACTIVE:
                logger.warning(f"Session {session['id']} is not active")
                return False

            # Check if session has been updated in the last 60 minutes
            last_update = datetime.fromisoformat(session['updated_at']).replace(tzinfo=timezone.utc)
            current_time = datetime.now(timezone.utc)
            if current_time - last_update > timedelta(minutes=60):
                logger.warning(f"Session {session['id']} has not been updated in over 60 minutes")
                await self.complete_session(session['id'])
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating session: {str(e)}")
            return False

    async def complete_session(self, session_id: UUID) -> None:
        """
        Marks a session as completed and sets the completed_at timestamp.
        """
        try:
            update_data = {
                "status": SessionStatus.COMPLETED,
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
    
            self.supabase.table("interview_sessions")\
                .update(update_data)\
                .eq("id", str(session_id))\
                .execute()
    
            logger.info(f"Completed session {session_id}")
    
        except Exception as e:
            logger.error(f"Error completing session {session_id}: {str(e)}")
            raise
    
    async def close_stale_sessions(self, profile_id: Optional[UUID] = None) -> None:
        """
        Closes stale sessions that haven't been updated in over 60 minutes.
        """
        try:
            sixty_minutes_ago = datetime.utcnow() - timedelta(minutes=60)
    
            # Build base query
            query = self.supabase.table("interview_sessions")\
                .select("id")\
                .eq("status", SessionStatus.ACTIVE)\
                .lt("updated_at", sixty_minutes_ago.isoformat())
    
            # Add profile filter if specified
            if profile_id:
                query = query.eq("profile_id", str(profile_id))
    
            # Get stale sessions
            result = query.execute()
    
            # Complete each stale session
            for session in result.data:
                await self.complete_session(session['id'])
    
            if len(result.data) > 0:
                logger.info(f"Closed {len(result.data)} stale sessions" + 
                           f" for profile {profile_id}" if profile_id else "")
    
        except Exception as e:
            logger.error(f"Error closing stale sessions: {str(e)}")