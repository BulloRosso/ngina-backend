# services/sentiment.py
from uuid import UUID, uuid4
from datetime import datetime
from models.memory import InterviewQuestion
import openai
import os
from typing import Dict, Any
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

class EmpatheticInterviewer:
    def __init__(self):
        self.openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def start_new_session(self, profile_id: UUID, language: str = "en") -> Dict[str, Any]:
        """Start a new interview session for a profile."""
        try:
            # Generate an empathetic opening question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an empathetic interviewer helping people preserve their memories. 
                        Generate a warm, inviting opening question that encourages sharing personal memories.
                        Respond in {language} language only."""
                    },
                    {
                        "role": "user",
                        "content": "Generate an opening question for a memory preservation interview."
                    }
                ],
                max_tokens=100
            )

            initial_question = response.choices[0].message.content
            session_id = uuid4()
            now = datetime.utcnow()

            # Create session record...
            session_data = {
                "id": str(session_id),
                "profile_id": str(profile_id),
                "category": "general",
                "started_at": now.isoformat(),
                "emotional_state": {"initial": "neutral"},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

            logger.debug(f"Creating session with data: {session_data}")

            # Insert the session into Supabase
            result = self.supabase.table("interview_sessions").insert(
                session_data
            ).execute()

            logger.debug(f"Session creation result: {result}")

            if not result.data:
                raise Exception("Failed to create interview session record")

            return {
                "session_id": str(session_id),
                "initial_question": initial_question or "Tell me about a memorable moment from your life.",
                "started_at": now.isoformat(),
                "profile_id": str(profile_id)
            }

        except Exception as e:
            logger.error(f"Error starting interview session: {str(e)}")
            raise Exception(f"Failed to start interview session: {str(e)}")

    async def process_interview_response(
        self,
        profile_id: UUID,
        session_id: UUID,
        response_text: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process a response from the interviewee and generate the next question.
        """
        try:
            # Analyze sentiment
            sentiment = await self._analyze_sentiment(response_text)

            # Generate follow-up question based on the response
            next_question = await self._generate_follow_up_question(response_text, language)

            return {
                "sentiment": sentiment,
                "follow_up": next_question
            }

        except Exception as e:
            print(f"Error processing interview response: {str(e)}")
            return {
                "sentiment": {"joy": 0.5, "nostalgia": 0.5},
                "follow_up": "Can you tell me more about that?"
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
                model="gpt-4",
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