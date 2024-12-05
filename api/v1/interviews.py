# api/v1/interviews.py
from fastapi import APIRouter, HTTPException
from typing import Optional
from uuid import UUID
from services.sentiment import EmpatheticInterviewer
from models.memory import InterviewResponse, InterviewQuestion

router = APIRouter(prefix="/interviews", tags=["interviews"])

@router.post("/{profile_id}/start")
async def start_interview(profile_id: UUID):
    interviewer = EmpatheticInterviewer()
    return await interviewer.start_new_session(profile_id)

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