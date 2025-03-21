# services/email.py
import os
from mailersend import emails
from pathlib import Path
import logging
import datetime
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Set default env variables for testing
        os.environ.setdefault('MAILERSEND_API_KEY', 'your-api-key')
        os.environ.setdefault('MAILERSEND_SENDER_EMAIL', 'noreply@noblivion.com')
        os.environ.setdefault('FRONTEND_URL', 'https://noblivion.com')

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

        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Load translations
        self.translations = self._load_translations()

        logger.debug(f"Email service initialized with frontend URL: {self.frontend_url}")

    def _load_translations(self):
        """Load all translation files from the i18n directory"""
        translations = {}
        i18n_path = Path('i18n')

        logger.info(f"Loading translations from: {i18n_path.absolute()}")

        if not i18n_path.exists():
            logger.warning("i18n directory not found")
            i18n_path.mkdir(parents=True)

        for locale_file in i18n_path.glob('*.json'):
            try:
                logger.info(f"Loading translation file: {locale_file}")
                with open(locale_file, 'r', encoding='utf-8') as f:
                    translations[locale_file.stem] = json.load(f)
            except Exception as e:
                logger.error(f"Error loading translation file {locale_file}: {str(e)}")

        if not translations:
            logger.error("No translation files found!")

        return translations

    def _get_translation(self, namespace: str, key: str, locale: str = 'en', **kwargs) -> str:
        """Get translated string for given namespace and key"""
        try:
            translation = self.translations.get(locale, {}).get(namespace, {}).get(
                key, 
                self.translations['en'].get(namespace, {}).get(key, f"{namespace}.{key}")
            )
            # Format the translation with provided variables
            return translation.format(**kwargs) if kwargs else translation
        except Exception as e:
            logger.error(f"Translation error for {locale}.{namespace}.{key}: {str(e)}")
            return f"{namespace}.{key}"

    def _render_template(self, template_name: str, locale: str = 'en', **kwargs) -> str:
        """Render a template with translations and variables"""
        try:
            template = self.jinja_env.get_template(f"{template_name}.html")

            # Get namespace from template name
            namespace = template_name.replace('-', '_')

            # Create translation function that handles absolute paths and parameters
            def translate(key, **trans_kwargs):
                # If the key starts with 'common', use it as absolute path
                if key.startswith('common.'):
                    return self._get_translation('common', key.split('.')[1], locale, **trans_kwargs)
                # Otherwise, use the template namespace
                return self._get_translation(namespace, key, locale, **trans_kwargs)

            # Add common variables
            common_vars = {
                'logo_url': f"{self.frontend_url}/img/title-logo.png",
                't': translate,  # Translation function
                'frontend_url': self.frontend_url,
                **kwargs  # Add all template variables to the root context
            }

            return template.render(**common_vars)

        except Exception as e:
            logger.error(f"Template rendering error: {str(e)}")
            raise

    async def send_email(
        self,
        template_name: str,
        to_email: str,
        subject_key: str,
        locale: str = 'en',
        **template_vars
    ):
        """Generic email sending method that supports any template and variables"""
        try:
            logger.info(f"Sending {template_name} email to {to_email} in {locale}")

            namespace = template_name.replace('-', '_')
            subject = self._get_translation(namespace, subject_key, locale, **template_vars)

            html_content = self._render_template(
                template_name,
                locale=locale,
                **template_vars
            )

            mail_body = self._create_mail_body(
                to_email=to_email,
                subject=subject,
                html_content=html_content
            )

            return self.mailer.send(mail_body)

        except Exception as e:
            logger.error(f"Failed to send {template_name} email: {str(e)}")
            raise

    def _create_mail_body(self, to_email: str, subject: str, html_content: str) -> dict:
        """Create a standardized mail body for MailerSend"""
        try:
            mail_body = {}

            mail_from = {
                "name": "nginA",
                "email": self.sender_domain
            }
            self.mailer.set_mail_from(mail_from, mail_body)

            recipients = [
                {
                    "name": to_email,
                    "email": to_email
                }
            ]
            self.mailer.set_mail_to(recipients, mail_body)

            self.mailer.set_subject(subject, mail_body)
            self.mailer.set_html_content(html_content, mail_body)

            plain_text = html_content.replace('<br>', '\n').replace('</p>', '\n\n')
            self.mailer.set_plaintext_content(plain_text, mail_body)

            return mail_body

        except Exception as e:
            logger.error(f"Error creating mail body: {str(e)}")
            raise