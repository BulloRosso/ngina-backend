# services/email.py
import os
from mailersend import emails
from pathlib import Path
from dotenv import load_dotenv
import logging
import datetime
import aiofiles

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.api_key = os.getenv('MAILERSEND_API_KEY')
        self.sender_domain = os.getenv('MAILERSEND_SENDER_EMAIL')
        self.mailer = emails.NewEmail(self.api_key)

    def _create_mail_body(
        self,
        to_email: str,
        subject: str,
        html_content: str
    ) -> dict:
        """Create a standardized mail body for MailerSend"""
        mail_body = {}

        # Set sender
        mail_from = {
            "name": "Noblivion",
            "email": self.sender_domain
        }
        self.mailer.set_mail_from(mail_from, mail_body)

        # Set recipient
        recipients = [
            {
                "name": to_email,
                "email": to_email
            }
        ]
        self.mailer.set_mail_to(recipients, mail_body)

        # Set subject
        self.mailer.set_subject(subject, mail_body)

        # Set content
        self.mailer.set_html_content(html_content, mail_body)

        # Create plain text version
        # Simple conversion - you might want to improve this
        plain_text = html_content.replace('<br>', '\n').replace('</p>', '\n\n')
        self.mailer.set_plaintext_content(plain_text, mail_body)

        return mail_body

    async def send_interview_invitation(self, to_email: str, profile_name: str, token: str, expires_at: str):
        try:
            # Read template
            template_path = Path("templates/interview-invitation.html")
            with open(template_path, "r") as f:
                html_content = f.read()

            # Format the date
            formatted_date = expires_at.strftime("%B %d, %Y")  # e.g., "December 24, 2024"
            
            # Replace placeholders
            html_content = html_content\
                .replace("{profile_name}", profile_name)\
                .replace("{interview_url}", f"{os.getenv('FRONTEND_URL')}/interview-token?token={token}")\
                .replace("{expiry_date}", formatted_date)

            # Create mail body
            mail_body = self._create_mail_body(
                to_email=to_email,
                subject=f"You're invited to share memories about {profile_name}",
                html_content=html_content
            )

            # Send email
            return self.mailer.send(mail_body)

        except Exception as e:
            logger.error(f"Failed to send invitation email: {str(e)}")
            raise

    async def send_expiry_reminder(self, to_email: str, profile_name: str, expires_at: str):
        try:
            template_path = Path("templates/expiry-reminder.html")
            with open(template_path, "r") as f:
                html_content = f.read()

            # Format the date
            formatted_date = expires_at.strftime("%B %d, %Y")
            
            html_content = html_content\
                .replace("{profile_name}", profile_name)\
                .replace("{expiry_date}", formatted_date)

            mail_body = self._create_mail_body(
                to_email=to_email,
                subject=f"Reminder: Interview invitation for {profile_name} expires soon",
                html_content=html_content
            )

            return self.mailer.send(mail_body)

        except Exception as e:
            logger.error(f"Failed to send expiry reminder: {str(e)}")
            raise