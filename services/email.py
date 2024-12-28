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
        self.frontend_url = os.getenv('FRONTEND_URL')

        if not self.api_key:
            raise ValueError("MAILERSEND_API_KEY not found in environment")
        if not self.sender_domain:
            raise ValueError("MAILERSEND_SENDER_EMAIL not found in environment")
        if not self.frontend_url:
            raise ValueError("FRONTEND_URL not found in environment")

        self.mailer = emails.NewEmail(self.api_key)
        logger.debug(f"Email service initialized with frontend URL: {self.frontend_url}")

    def _create_mail_body(
        self,
        to_email: str,
        subject: str,
        html_content: str
    ) -> dict:
        """Create a standardized mail body for MailerSend"""
        try:
            # Replace logo URL in template
            logo_url = f"{self.frontend_url}/conch-logo-small.png"
            logger.debug(f"Using logo URL: {logo_url}")
            html_content = html_content.replace("{logo_url}", logo_url)

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
            plain_text = html_content.replace('<br>', '\n').replace('</p>', '\n\n')
            self.mailer.set_plaintext_content(plain_text, mail_body)

            return mail_body

        except Exception as e:
            logger.error(f"Error creating mail body: {str(e)}")
            raise

    async def send_bug_report(self, to_email: str, subject: str, html_content: str):
        """Send bug report email."""
        try:
            # Create mail body
            mail_body = self._create_mail_body(
                to_email=to_email,
                subject=f"Bug Report: {subject}",
                html_content=html_content
            )

            # Send email
            return self.mailer.send(mail_body)

        except Exception as e:
            logger.error(f"Failed to send bug report email: {str(e)}")
            raise

    async def send_confirmation_email(self, to_email: str, confirmation_link: str):
        """Send email confirmation link to user."""
        try:
            # Read template
            template_path = Path("templates/email-confirmation.html")
            async with aiofiles.open(template_path, "r") as f:
                html_content = await f.read()

            # Replace placeholders
            html_content = html_content.replace("{confirmation_url}", confirmation_link)

            # Create mail body
            mail_body = self._create_mail_body(
                to_email=to_email,
                subject="Confirm your Noblivion account",
                html_content=html_content
            )

            # Send email
            return self.mailer.send(mail_body)

        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")
            raise
            
    async def send_interview_invitation(self, to_email: str, profile_name: str, token: str, expires_at: str):
        try:
            logger.info("Sending interview invitation email")
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

            logger.info("Sending email to " + to_email)

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

    async def send_password_reset_email(self, to_email: str, reset_token: str):
        """Send password reset email with reset token link."""
        try:
            # Read template
            template_path = Path("templates/password-reset.html")
            with open(template_path, "r") as f:
                html_content = f.read()
    
            # Replace placeholders
            reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={reset_token}"
            html_content = html_content.replace("{reset_url}", reset_url)
    
            # Create mail body
            mail_body = self._create_mail_body(
                to_email=to_email,
                subject="Reset Your Noblivion Password",
                html_content=html_content
            )
    
            # Send email
            return self.mailer.send(mail_body)
    
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            raise