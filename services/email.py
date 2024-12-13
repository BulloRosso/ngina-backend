# services/email.py
import os
from mailersend import emails
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.api_key = os.getenv('MAILERSEND_API_KEY')
        self.sender_domain = os.getenv('MAILERSEND_SENDER_EMAIL')
        self.mailer = emails.NewEmail(self.api_key)

    def send_verification_email(self, to_email: str, verification_code: str):
        try:
            # Read template
            template_path = Path("templates/account-verification-en.html")
            with open(template_path, "r") as f:
                html_content = f.read()

            # Replace placeholder
            html_content = html_content.replace("{verification_code}", verification_code)

            # Prepare empty mail body
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
            self.mailer.set_subject("Verify your Noblivion account", mail_body)

            # Set content
            self.mailer.set_html_content(html_content, mail_body)
            self.mailer.set_plaintext_content(
                f"Your verification code is: {verification_code}", 
                mail_body
            )

            # Send email synchronously
            return self.mailer.send(mail_body)

        except Exception as e:
            print(f"Failed to send verification email: {str(e)}")
            raise