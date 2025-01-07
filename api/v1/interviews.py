# api/v1/interviews.py
from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from services.sentiment import EmpatheticInterviewer, SessionStatus
from models.memory import InterviewResponse, InterviewQuestion
import logging
from datetime import datetime, timedelta, timezone
from openai import OpenAI
import os
from starlette.websockets import WebSocketDisconnect
import asyncio
import urllib.parse
from dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

class SessionStatus:
    ACTIVE = "active"
    COMPLETED = "completed"

async def verify_profile_ownership(profile_id: UUID, user_id: UUID, interviewer: EmpatheticInterviewer):
    """Verify that the user owns the profile"""
    profile_result = interviewer.supabase.table("profiles")\
        .select("user_id")\
        .eq("id", str(profile_id))\
        .single()\
        .execute()

    if not profile_result.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    if str(profile_result.data["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Access forbidden")

@router.post("/{profile_id}/start")
async def start_interview(
    profile_id: UUID, 
    language: str = "en",
    user_id: UUID = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        interviewer = EmpatheticInterviewer()

        # Verify profile ownership
        await verify_profile_ownership(profile_id, user_id, interviewer)

        session = await interviewer.get_or_create_session(profile_id) 
        question, memory_id = await interviewer.get_initial_question(profile_id, language)

        return {
            "session_id": session["id"],
            "initial_question": question,
            "started_at": session["started_at"],
            "memory_id": memory_id
        }
    except Exception as e:
        logger.error(f"Start interview error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/response")
async def process_response(
    session_id: UUID,
    response: InterviewResponse,
    user_id: UUID = Depends(get_current_user)
):
    try:
        interviewer = EmpatheticInterviewer()

        # Get session data
        session_result = interviewer.supabase.table("interview_sessions")\
            .select("*,profiles!inner(user_id)")\
            .eq("id", str(session_id))\
            .single()\
            .execute()

        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify ownership
        if str(session_result.data["profiles"]["user_id"]) != str(user_id):
            raise HTTPException(status_code=403, detail="Access forbidden")

        session = session_result.data
        profile_id = UUID(session['profile_id'])

        # Verify session is still valid
        if not await interviewer.validate_session(session):
            raise HTTPException(status_code=400, detail="Session expired or inactive")

        # Process the response
        result = await interviewer.process_interview_response(
            user_id=response.user_id,
            profile_id=profile_id,
            session_id=session_id,
            response_text=response.text,
            language=response.language,
            memory_id=response.memory_id 
        )

        # Update session timestamp
        interviewer.supabase.table("interview_sessions")\
            .update({"updated_at": datetime.utcnow().isoformat()})\
            .eq("id", str(session_id))\
            .execute()

        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process response: {str(e)}"
        )

@router.post("/{session_id}/next_question")
async def get_next_question(
    session_id: UUID,
    language: str = Query(default="en"),
    user_id: UUID = Depends(get_current_user)
) -> Dict[str, str]:
    try:
        interviewer = EmpatheticInterviewer()

        # Get current session
        session_result = interviewer.supabase.table("interview_sessions")\
            .select("*,profiles!inner(user_id)")\
            .eq("id", str(session_id))\
            .single()\
            .execute()

        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify ownership
        if str(session_result.data["profiles"]["user_id"]) != str(user_id):
            raise HTTPException(status_code=403, detail="Access forbidden")

        session = session_result.data

        # Verify session is active
        if not await interviewer.validate_session(session):
            raise HTTPException(status_code=400, detail="Session expired or inactive")

        # Get next question based on last_question field
        if not session.get('last_question'):
            question, _ = await interviewer.get_initial_question(
                UUID(session['profile_id']),
                language
            )
        else:
            question = await interviewer.generate_next_question(
                UUID(session['profile_id']),
                session_id,
                language
            )

        # Update session with current question and timestamp
        interviewer.supabase.table("interview_sessions")\
            .update({
                "last_question": question,
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", str(session_id))\
            .execute()

        return {"text": question}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting next question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/end")
async def end_interview(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user)
) -> Dict[str, str]:
    try:
        interviewer = EmpatheticInterviewer()

        # Verify session ownership
        session_result = interviewer.supabase.table("interview_sessions")\
            .select("profiles!inner(user_id)")\
            .eq("id", str(session_id))\
            .single()\
            .execute()

        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        if str(session_result.data["profiles"]["user_id"]) != str(user_id):
            raise HTTPException(status_code=403, detail="Access forbidden")

        # Complete the session
        await interviewer.complete_session(session_id)
        return {"message": "Session ended successfully"}

    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{profile_id}/sessions")
async def get_interview_sessions(
    profile_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    try:
        interviewer = EmpatheticInterviewer()

        # Verify profile ownership
        await verify_profile_ownership(profile_id, user_id, interviewer)

        result = interviewer.supabase.table("interview_sessions")\
            .select("""
                id,
                started_at,
                completed_at,
                status,
                emotional_state,
                summary,
                topics_of_interest
            """)\
            .eq("profile_id", str(profile_id))\
            .order("started_at", desc=True)\
            .execute()

        if not result.data:
            return []

        sessions = []
        for session in result.data:
            try:
                if session.get('started_at'):
                    session['started_at'] = datetime.fromisoformat(session['started_at'])
                if session.get('completed_at'):
                    session['completed_at'] = datetime.fromisoformat(session['completed_at'])

                logger.info(f"Processing session {session['id']} for profile {profile_id}")
                sessions.append(session)
            except Exception as e:
                logger.error(f"Error processing session {session.get('id')}: {str(e)}")
                continue

        return sessions

    except Exception as e:
        logger.error(f"Error fetching interview sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch interview sessions: {str(e)}"
        )

@router.websocket("/tts/{text_to_read}")
async def text_to_speech(websocket: WebSocket, text_to_read: str):
    try:
        await websocket.accept()

        # Here we could add authentication for WebSocket,
        # but since it's a single-use connection for TTS,
        # rate limiting might be more appropriate

        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        try:
            decoded_text = urllib.parse.unquote(text_to_read)
            logger.info(f"Processing TTS for text: {decoded_text[:50]}...")

            await websocket.send_text('|AUDIO_START|')

            with openai_client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="nova",
                response_format="mp3",
                input=decoded_text,
            ) as response:
                for chunk in response.iter_bytes(chunk_size=1024):
                    await websocket.send_bytes(chunk)

            await websocket.send_text('|AUDIO_END|')

        except WebSocketDisconnect:
            logger.info("Client disconnected normally")
            return

        except Exception as e:
            logger.error(f"Error processing TTS request: {str(e)}")
            try:
                await websocket.send_text(f"Error: {str(e)}")
            except:
                pass

    except Exception as e:
        logger.error(f"Error in TTS websocket: {str(e)}")

    finally:
        try:
            await websocket.close()
        except:
            pass

@router.post("/summarize")
async def summarize_interviews(user_id: UUID = Depends(get_current_user)):
    try:
        interviewer = EmpatheticInterviewer()
        client = OpenAI()

        # Get completed sessions without summaries
        sessions_result = interviewer.supabase.table("interview_sessions")\
            .select("*,profiles!inner(user_id)")\
            .eq("status", SessionStatus.COMPLETED)\
            .is_("summary", "null")\
            .execute()

        if not sessions_result.data:
            return {"message": "No sessions to summarize"}

        for session in sessions_result.data:
            # Verify ownership of each session
            if str(session["profiles"]["user_id"]) != str(user_id):
                logger.warning(f"Unauthorized summary attempt for session {session['id']}")
                continue

            start_date = session['started_at']
            end_date = session.get('completed_at') or datetime.utcnow().isoformat()

            memories_result = interviewer.supabase.table("memories")\
                .select("description")\
                .eq("profile_id", session['profile_id'])\
                .gte("created_at", start_date)\
                .lte("created_at", end_date)\
                .or_(f"updated_at.gte.{start_date},updated_at.lte.{end_date}")\
                .execute()

            if not memories_result.data:
                continue

            memory_text = " ".join(m['description'] for m in memories_result.data)

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional writer. Summarize the following text into 2 or 3 short sentences. Focus on the important things and do not include any details"
                    },
                    {
                        "role": "user",
                        "content": memory_text
                    }
                ],
                temperature=0.2
            )

            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary for session {session['id']}: {summary}")

            interviewer.supabase.table("interview_sessions")\
                .update({"summary": summary})\
                .eq("id", session['id'])\
                .execute()

        return {"message": "Summaries generated successfully"}

    except Exception as e:
        logger.error(f"Error generating summaries: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summaries: {str(e)}"
        )