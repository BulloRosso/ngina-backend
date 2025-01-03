# api/v1/interviews.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from uuid import UUID, uuid4
from services.sentiment import EmpatheticInterviewer
from models.memory import InterviewResponse, InterviewQuestion
import logging
from datetime import datetime, timedelta
from fastapi import WebSocket
from openai import OpenAI
import os
from starlette.websockets import WebSocketDisconnect
import asyncio
import urllib.parse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

class SessionStatus:
    ACTIVE = "active"
    COMPLETED = "completed"

@router.post("/{profile_id}/start")
async def start_interview(profile_id: UUID, language: str = "en"):
    """Start or resume an interview session"""
    try:
        interviewer = EmpatheticInterviewer()

        # Calculate timestamp from 60 minutes ago
        sixty_minutes_ago = datetime.utcnow() - timedelta(minutes=60)

        # Query for recent active session
        result = interviewer.supabase.table("interview_sessions")\
            .select("*")\
            .eq("profile_id", str(profile_id))\
            .eq("status", SessionStatus.ACTIVE)\
            .gte("updated_at", sixty_minutes_ago.isoformat())\
            .order("started_at", desc=True)\
            .limit(1)\
            .execute()

        # If recent active session exists, use it
        if result.data:
            session = result.data[0]
            logger.info(f"Reusing existing session {session['id']} for profile {profile_id}")

            # Generate question using existing session
            question = await interviewer.generate_next_question(profile_id, session['id'], language)

            return {
                "session_id": session['id'],
                "initial_question": question
            }

        # No recent session found, create new one
        session_data = {
            "id": str(uuid4()),
            "profile_id": str(profile_id),
            "category": "initial",
            "started_at": datetime.utcnow().isoformat(),
            "emotional_state": {"initial": "neutral"},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": SessionStatus.ACTIVE
        }

        # Insert new session
        result = interviewer.supabase.table("interview_sessions")\
            .insert(session_data)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create session")

        new_session = result.data[0]
        logger.info(f"Created new session {new_session['id']} for profile {profile_id}")

        # Generate initial question
        question = await interviewer.generate_next_question(profile_id, new_session['id'], language)

        return {
            "session_id": new_session['id'],
            "initial_question": question
        }

    except Exception as e:
        logger.error(f"Error in start_interview: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start interview: {str(e)}"
        )

@router.post("/{profile_id}/response")
async def process_response(
    profile_id: UUID,
    response: InterviewResponse,
    session_id: UUID = Query(...)
):
    """Process a response and update session"""
    try:
        interviewer = EmpatheticInterviewer()

        # Verify session is active and recent
        session_result = interviewer.supabase.table("interview_sessions")\
            .select("*")\
            .eq("id", str(session_id))\
            .eq("status", SessionStatus.ACTIVE)\
            .execute()

        if not session_result.data:
            raise HTTPException(
                status_code=400, 
                detail="Session not found or no longer active"
            )

        session = session_result.data[0]

        # Check if session is too old
        updated_at = datetime.fromisoformat(session['updated_at'])
        if datetime.utcnow() - updated_at > timedelta(minutes=60):
            # Auto-complete old session
            interviewer.supabase.table("interview_sessions")\
                .update({
                    "status": SessionStatus.COMPLETED,
                    "completed_at": datetime.utcnow().isoformat()
                })\
                .eq("id", str(session_id))\
                .execute()

            raise HTTPException(
                status_code=400,
                detail="Session expired. Please start a new session."
            )

        # Process the response
        result = await interviewer.process_interview_response(
            user_id=response.user_id,
            profile_id=profile_id,
            session_id=session_id,
            response_text=response.text,
            language=response.language
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

@router.get("/{profile_id}/sessions")
async def get_interview_sessions(profile_id: UUID):
    """Get all interview sessions for a profile, excluding the initial backstory session"""
    try:
        interviewer = EmpatheticInterviewer()

        # Query sessions, excluding the initial backstory session
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
            .neq("category", "initial")\
            .order("started_at", desc=True)\
            .execute()

        if not result.data:
            return []

        # Process dates and format response
        sessions = []
        for session in result.data:
            try:
                # Parse timestamps if they exist
                if session.get('started_at'):
                    session['started_at'] = datetime.fromisoformat(session['started_at'])
                if session.get('completed_at'):
                    session['completed_at'] = datetime.fromisoformat(session['completed_at'])

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
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        try:
            # Decode the URL-encoded text
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