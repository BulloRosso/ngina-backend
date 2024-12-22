# api/v1/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
import logging
from services.knowledgemanagement import KnowledgeManagement

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
        answer = await knowledge_manager.query_with_rag(query.query_text)

        logger.debug(f"Generated response: {answer}")
        return ChatResponse(answer=answer)

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )