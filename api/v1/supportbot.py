# api/v1/supportbot.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Literal, List
from services.email import EmailService
from openai import OpenAI
from pathlib import Path
import logging
import os
import aiofiles
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
import psycopg
from datetime import datetime
from uuid import UUID
from dependencies.auth import get_current_user  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI()

router = APIRouter(prefix="/supportbot", tags=["bots"])

# PostgreSQL connection settings
POSTGRES_CONNECTION = os.getenv("REPLIT_POSTGRES_CONNECTION")

class BugReportRequest(BaseModel):
    severity: Literal['Feature Request', 'Bug', 'Severe Bug']
    subject: str
    message: str
    userEmail: str

class SupportBotRequest(BaseModel):
    message: str
    language: str = "en"  # session_id removed as it's now from auth

class SupportBotResponse(BaseModel):
    answer: str

def initialize_chat_history():
    """Initialize PostgreSQL tables for chat history if they don't exist."""
    try:
        conn = psycopg.connect(POSTGRES_CONNECTION)
        PostgresChatMessageHistory.create_tables(conn, "chat_history")
        conn.close()
        logger.info("Chat history tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize chat history tables: {e}")
        raise

# Initialize tables on startup
initialize_chat_history()

def get_chat_history(user_id: UUID) -> List[BaseMessage]:
    """Retrieve chat history for a user."""
    try:
        conn = psycopg.connect(POSTGRES_CONNECTION)
        history = PostgresChatMessageHistory(
            "chat_history",
            str(user_id),  # Convert UUID to string for storage
            sync_connection=conn
        )
        messages = history.get_messages()
        conn.close()
        # Keep only the last 10 messages
        return messages[-10:] if messages else []
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        return []

def store_messages(user_id: UUID, user_message: str, bot_response: str):
    """Store new messages in the chat history."""
    try:
        conn = psycopg.connect(POSTGRES_CONNECTION)
        history = PostgresChatMessageHistory(
            "chat_history",
            str(user_id),  # Convert UUID to string for storage
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

@router.post("/bugreport")
async def submit_bug_report(
    report: BugReportRequest,
    user_id: UUID = Depends(get_current_user)
):
    try:
        # Initialize email service
        email_service = EmailService()

        # Send the email
        await email_service.send_email(
            template_name='bug-report',
            to_email="ralph.goellner@e-ntegration.de",
            subject_key='subject',
            locale='en',
            severity=report.severity,
            subject=report.subject,
            message=report.message,
            user_email=report.userEmail
        )

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Failed to submit bug report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to submit bug report"
        )

def load_prompt_template() -> str:
    """Load the prompt template from file."""
    try:
        prompt_path = Path("prompts/supportbot.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt template: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load prompt template"
        )

# Cache the prompt template
PROMPT_TEMPLATE = load_prompt_template()

@router.post("", response_model=SupportBotResponse)
async def get_support_response(
    request: SupportBotRequest,
    user_id: UUID = Depends(get_current_user)
) -> SupportBotResponse:
    """Process a support request with persistent memory and return a response."""
    try:
        # Get chat history for the authenticated user
        chat_history = get_chat_history(user_id)

        # Format chat history for the prompt
        history_text = ""
        if chat_history:
            history_text = "\n\nPrevious conversation:\n" + "\n".join(
                f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content}"
                for msg in chat_history
            )

        # Prepare the prompt with history
        prompt = PROMPT_TEMPLATE.format(
            input=request.message,
            language=request.language
        ) + history_text

        # Get response from OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a support bot for the nOblivion application. Always respond in {request.language}."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7
        )

        # Extract the response text
        response_text = response.choices[0].message.content.strip()

        # Basic validation of response
        if not response_text:
            raise ValueError("Empty response from model")

        # Store the conversation in PostgreSQL using the user's UUID
        store_messages(user_id, request.message, response_text)

        # Validate that all tags are properly closed
        if response_text.count("<TopicButton") != response_text.count("/>"):
            logger.warning("Malformed TopicButton tags in response")
            response_text = response_text.replace("</TopicButton>", "/>")

        return SupportBotResponse(answer=response_text)

    except Exception as e:
        logger.error(f"Error processing support request: {e}")
        error_messages = {
            "de": "Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.",
            "en": "Sorry, an error occurred. Please try again later."
        }
        return SupportBotResponse(
            answer=error_messages.get(request.language, error_messages["en"])
        )