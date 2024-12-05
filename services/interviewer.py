# services/interviewer.py
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import openai
from models.memory import Memory, InterviewQuestion, Category
from models.profile import Profile

class MemoryInterviewer:
    def __init__(self):
        self.openai = openai

    async def start_new_session(self, profile_id: UUID):
        try:
            profile = await self._get_profile(profile_id)
            session = {
                'profile_id': profile_id,
                'started_at': datetime.now(),
                'category': self._determine_next_category(profile_id)
            }
            return await self._create_session(session)
        except Exception as e:
            raise ValueError(f"Failed to start session: {str(e)}")

    async def generate_interview_prompt(self, profile_id: UUID, session_id: UUID) -> InterviewQuestion:
        try:
            profile = await self._get_profile(profile_id)
            previous_memories = await self._get_recent_memories(profile_id)
            session = await self._get_session(session_id)

            prompt = self._construct_prompt(profile, previous_memories, session)
            response = await self.openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self._get_system_prompt(profile)},
                    {"role": "user", "content": prompt}
                ]
            )

            return InterviewQuestion(
                text=response.choices[0].message.content,
                context=session['category'],
                suggested_topics=self._extract_topics(response)
            )
        except Exception as e:
            raise ValueError(f"Failed to generate prompt: {str(e)}")

    async def end_session(self, session_id: UUID):
        try:
            session = await self._get_session(session_id)
            session['completed_at'] = datetime.now()
            return await self._update_session(session)
        except Exception as e:
            raise ValueError(f"Failed to end session: {str(e)}")

    # Helper methods to be implemented
    async def _get_profile(self, profile_id: UUID):
        pass

    async def _get_session(self, session_id: UUID):
        pass

    async def _create_session(self, session: dict):
        pass

    async def _update_session(self, session: dict):
        pass

    async def _get_recent_memories(self, profile_id: UUID):
        pass