# api/v1/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
import logging
from services.knowledgemanagement import KnowledgeManagement
import datetime
from supabase import create_client
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatQuery(BaseModel):
    profile_id: UUID
    query_text: str

class ChatResponse(BaseModel):
    answer: str


@router.post("", response_model=ChatResponse)
async def process_chat_message(query: ChatQuery):
    try:
        logger.info(f"Processing chat message for profile {query.profile_id}")
        logger.debug(f"Query text: {query.query_text}")

        # Initialize knowledge management and use RAG
        knowledge_manager = KnowledgeManagement()
        answer = await knowledge_manager.query_with_rag(query.query_text, str(query.profile_id))

        # Create interaction data
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
        
        logger.debug(f"Generated response: {answer}")
        return ChatResponse(answer=answer)

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )