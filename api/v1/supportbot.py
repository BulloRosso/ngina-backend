# api/v1/supportbot.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from services.email import EmailService
from openai import OpenAI
from pathlib import Path
import logging
import os
import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI()

router = APIRouter(prefix="/supportbot", tags=["bots"])

class BugReportRequest(BaseModel):
    severity: Literal['Feature Request', 'Bug', 'Severe Bug']
    subject: str
    message: str
    userEmail: str
    
class SupportBotRequest(BaseModel):
    message: str
    language: str = "en"  # default to English if not specified

class SupportBotResponse(BaseModel):
    answer: str

@router.post("/bugreport")
async def submit_bug_report(report: BugReportRequest):
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
async def get_support_response(request: SupportBotRequest) -> SupportBotResponse:
    """
    Process a support request and return a response.

    The response may include special tags for UI components:
    - <BugReport/> for the bug report form
    - <TopicButton cmd="COMMAND" /> for topic suggestion buttons
    """
    try:
        # Prepare the prompt
        prompt = PROMPT_TEMPLATE.format(
            input=request.message,
            language=request.language
        )

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

        # Validate that all tags are properly closed
        if response_text.count("<TopicButton") != response_text.count("/>"):
            logger.warning("Malformed TopicButton tags in response")
            # Try to fix common issues
            response_text = response_text.replace("</TopicButton>", "/>")

        return SupportBotResponse(answer=response_text)

    except Exception as e:
        logger.error(f"Error processing support request: {e}")
        # Return a user-friendly error message in the appropriate language
        error_messages = {
            "de": "Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.",
            "en": "Sorry, an error occurred. Please try again later."
        }
        return SupportBotResponse(
            answer=error_messages.get(request.language, error_messages["en"])
        )