# api/v1/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
import logging
from services.knowledgemanagement import KnowledgeManagement
import datetime
from supabase import create_client
import os
import psycopg
from typing import List
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from services.profile import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# PostgreSQL connection settings
POSTGRES_CONNECTION = os.getenv("REPLIT_POSTGRES_CONNECTION")

class ChatQuery(BaseModel):
    profile_id: UUID
    query_text: str

class ChatResponse(BaseModel):
    answer: str

async def get_chat_history(profile_id: UUID) -> List[BaseMessage]:
    """Retrieve chat history for a profile."""
    try:
        conn = psycopg.connect(POSTGRES_CONNECTION)
        history = PostgresChatMessageHistory(
            "chat_history",
            str(profile_id),
            sync_connection=conn
        )
        messages = history.get_messages()
        conn.close()
        # Keep only the last 10 messages
        return messages[-10:] if messages else []
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        return []

async def store_messages(profile_id: UUID, user_message: str, bot_response: str):
    """Store new messages in the chat history."""
    try:
        conn = psycopg.connect(POSTGRES_CONNECTION)
        history = PostgresChatMessageHistory(
            "chat_history",
            str(profile_id),
            sync_connection=conn
        )

        # Add the new messages
        history.add_messages([
            HumanMessage(content=user_message),
            AIMessage(content=bot_response)
        ])

        conn.close()
    except Exception as e:
        logger.error(f"Failed to store messages: {e}")

async def get_system_prompt(profile_id: UUID) -> str:
    """Get personalized system prompt based on profile data."""
    try:
        profile_service = ProfileService()
        profile = await profile_service.get_profile(profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Format birth date
        birth_date = profile.date_of_birth.strftime("%B %d, %Y")

        # Get backstory from metadata if it exists
        backstory = profile.metadata.get('backstory', '') if profile.metadata else ''
        backstory_context = f" Your backstory is: {backstory}" if backstory else ""

        # Construct system prompt
        system_prompt = (
            f"You are the virtual incarnation of {profile.first_name} {profile.last_name}. "
            f"You were born on {birth_date} in {profile.place_of_birth}."
            f"{backstory_context}"
            "\nRespond to all questions from this perspective, using your knowledge "
            "and memories to engage in authentic conversation. When you don't know "
            "something specific from your memories, you can draw upon general knowledge "
            "that would be reasonable for someone with your background."
        )

        logger.info(f"System prompt: {system_prompt}")

        return system_prompt
    except Exception as e:
        logger.error(f"Failed to generate system prompt: {e}")
        raise

@router.post("", response_model=ChatResponse)
async def process_chat_message(query: ChatQuery):
    try:
        logger.info(f"Processing chat message for profile {query.profile_id}")
        logger.debug(f"Query text: {query.query_text}")

        # Get system prompt based on profile
        system_prompt = await get_system_prompt(query.profile_id)

        # Get chat history for this profile
        chat_history = await get_chat_history(query.profile_id)

        # Format chat history for context
        history_text = ""
        if chat_history:
            history_text = "\n\nPrevious conversation:\n" + "\n".join(
                f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content}"
                for msg in chat_history
            )

        # Initialize knowledge management and use RAG with history context
        knowledge_manager = KnowledgeManagement()
        answer = await knowledge_manager.query_with_rag(
            query_text=query.query_text + history_text,
            profile_id=str(query.profile_id),
            system_prompt=system_prompt  # Pass the personalized system prompt
        )

        # Create interaction data for Supabase
        interaction_data = {
            "interaction": {
                "message": {
                    "user": query.query_text,
                    "agent": answer
                }
            },
            "profile_id": str(query.profile_id),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        # Save to Supabase
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        result = supabase_client.table("chat_interactions").insert(interaction_data).execute()
        if not result.data:
            logger.warning("Failed to save chat interaction")

        # Store the conversation in chat history
        await store_messages(query.profile_id, query.query_text, answer)

        logger.debug(f"Generated response: {answer}")
        return ChatResponse(answer=answer)

    except Exception as e:
        error_message = str(e)[:60]  # Get first 60 characters of error
        logger.error(f"Error processing chat message: {str(e)}")
        # Return friendly error message with truncated error details
        return ChatResponse(
            answer=f"Ups... I don't feel well right now... ({error_message})"
        )