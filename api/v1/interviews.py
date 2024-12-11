# api/v1/interviews.py
from fastapi import APIRouter, HTTPException
from typing import Optional
from uuid import UUID
from services.sentiment import EmpatheticInterviewer
from models.memory import InterviewResponse, InterviewQuestion
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

@router.post("/{profile_id}/start")
async def start_interview(profile_id: UUID, language: str = "en"):
    interviewer = EmpatheticInterviewer()
    return await interviewer.start_new_session(profile_id, language)

@router.post("/{profile_id}/response")
async def process_response(
    profile_id: UUID,
    response: InterviewResponse,
    session_id: UUID
):
    interviewer = EmpatheticInterviewer()
    return await interviewer.process_interview_response(
        profile_id,
        session_id,
        response.text,
        response.language
    )

@router.get("/{profile_id}/question")
async def get_next_question(
    profile_id: UUID,
    session_id: UUID,
    language: str = "en"
):
    """Get the next interview question based on the session context."""
    try:
        interviewer = EmpatheticInterviewer()
        result = await interviewer.generate_next_question(profile_id, session_id, language)
        return {
            "text": result,
            "suggested_topics": [],
            "requires_media": False
        }
    except Exception as e:
        logger.error(f"Error generating next question: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate next question"
        )