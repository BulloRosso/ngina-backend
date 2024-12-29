# test-email-templates.py
import asyncio
import argparse
from services.email import EmailService
import logging
import os
from datetime import datetime, timedelta

os.environ['MAILERSEND_API_KEY'] = 'mlsn.b8ab032ec666b2dac52de97709852e7c36fe2cbc85f9afa24351775078bfa5bf'
os.environ['MAILERSEND_SENDER_EMAIL'] = 'noreply@e-ntegration.de'
os.environ['FRONTEND_URL'] = 'https://8ede5a9c-1536-4919-b14f-82f6fd92faca-00-bvc5u3f2ay1d.janeway.replit.dev'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_account_verification(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing account verification template in {language}")
    return await service.send_email(
        template_name='account-verification',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        verification_code="123456"
    )

async def test_email_confirmation(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing email confirmation template in {language}")
    return await service.send_email(
        template_name='email-confirmation',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        confirmation_url="https://noblivion.com/confirm?token=sample-token"
    )

async def test_interview_invitation(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing interview invitation template in {language}")
    expiry_date = (datetime.now() + timedelta(days=14)).strftime("%B %d, %Y")
    return await service.send_email(
        template_name='interview-invitation',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        profile_name="Maria Schmidt",
        interview_url="https://noblivion.com/interview?token=sample-token",
        expiry_date=expiry_date
    )

async def test_expiry_reminder(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing expiry reminder template in {language}")
    expiry_date = (datetime.now() + timedelta(days=2)).strftime("%B %d, %Y")
    return await service.send_email(
        template_name='expiry-reminder',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        profile_name="Maria Schmidt",
        interview_url="https://noblivion.com/interview?token=sample-token",
        expiry_date=expiry_date
    )

async def test_invitation_extended(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing invitation extended template in {language}")
    expiry_date = (datetime.now() + timedelta(days=14)).strftime("%B %d, %Y")
    return await service.send_email(
        template_name='invitation-extended',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        profile_name="Maria Schmidt",
        interview_url="https://noblivion.com/interview?token=sample-token",
        expiry_date=expiry_date
    )

async def test_password_reset(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing password reset template in {language}")
    return await service.send_email(
        template_name='password-reset',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        reset_url="https://noblivion.com/reset-password?token=sample-token"
    )

async def test_bug_report(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing bug report template in {language}")
    return await service.send_email(
        template_name='bug-report',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        user_email="user@example.com",
        severity="High",
        subject="Login Screen Error",
        message="Unable to log in after password reset"
    )

async def test_waitlist_notification_user(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing waitlist notification (user) template in {language}")
    return await service.send_email(
        template_name='waitlist-notification-user',
        to_email=recipient,
        subject_key='subject',
        locale=language
    )

async def test_waitlist_notification_manufacturer(service: EmailService, recipient: str, language: str):
    logger.info(f"Testing waitlist notification (manufacturer) template in {language}")
    registration_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return await service.send_email(
        template_name='waitlist-notification-manufacturer',
        to_email=recipient,
        subject_key='subject',
        locale=language,
        user_email="new-user@example.com",
        registration_time=registration_time
    )

async def main():
    parser = argparse.ArgumentParser(description='Test email templates')
    parser.add_argument('--language', default='en', help='Language code (e.g., en, de)')
    parser.add_argument('--recipient', default='ralph.goellner@e-ntegration.de', help='Email recipient')
    parser.add_argument('--template', help='Specific template to test (optional)')

    # Add environment variable overrides
    parser.add_argument('--api-key', help='MailerSend API Key')
    parser.add_argument('--sender-email', help='Sender email address')
    parser.add_argument('--frontend-url', help='Frontend URL')

    args = parser.parse_args()

    # Set environment variables if provided
    if args.api_key:
        os.environ['MAILERSEND_API_KEY'] = args.api_key
    if args.sender_email:
        os.environ['MAILERSEND_SENDER_EMAIL'] = args.sender_email
    if args.frontend_url:
        os.environ['FRONTEND_URL'] = args.frontend_url

    service = EmailService()

    # Map of all test functions
    test_functions = {
        'account-verification': test_account_verification,
        'email-confirmation': test_email_confirmation,
        'interview-invitation': test_interview_invitation,
        'expiry-reminder': test_expiry_reminder,
        'invitation-extended': test_invitation_extended,
        'password-reset': test_password_reset,
        'bug-report': test_bug_report,
        'waitlist-notification-user': test_waitlist_notification_user,
        'waitlist-notification-manufacturer': test_waitlist_notification_manufacturer
    }

    try:
        if args.template:
            if args.template not in test_functions:
                logger.error(f"Unknown template: {args.template}")
                logger.info(f"Available templates: {', '.join(test_functions.keys())}")
                return

            logger.info(f"Testing single template: {args.template}")
            result = await test_functions[args.template](service, args.recipient, args.language)
            logger.info(f"Test result: {result}")
        else:
            logger.info(f"Testing all templates in {args.language}")
            for template_name, test_func in test_functions.items():
                logger.info(f"\nTesting template: {template_name}")
                result = await test_func(service, args.recipient, args.language)
                logger.info(f"Test result: {result}")
                await asyncio.sleep(1)  # Small delay between tests

        logger.info("Template testing completed successfully")

    except Exception as e:
        logger.error(f"Error during template testing: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())