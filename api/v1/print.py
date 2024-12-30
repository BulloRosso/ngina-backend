# api/v1/print.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from services.memory import MemoryService
from services.email import EmailService
import docraptor
import os
import logging
import uuid
from pathlib import Path
import asyncio
from datetime import datetime
from supabase import create_client, Client, AuthApiError
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape


router = APIRouter(prefix="/print", tags=["print"])

class PrintRequest(BaseModel):
    template: Literal['professional', 'warm', 'romantic']
    sortOrder: Literal['category', 'timestamp']

def get_image_url(url: str) -> str:
    if url and not url.startswith('http'):
        frontend_url = os.getenv('FRONTEND_URL', '').rstrip('/')
        return f"{frontend_url}/{url.lstrip('/')}"
    return url

class PDFGenerator:
    def __init__(self):
        template_dir = Path(__file__).parent.parent.parent / "pdf-templates"
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
        self.frontend_url = os.getenv('FRONTEND_URL', '').rstrip('/')

    def _format_memory_data(self, memory: dict) -> dict:
        date_str = (memory["time_period"].year 
                   if memory["time_period"].month == 1 and memory["time_period"].day == 1 
                   else memory["time_period"].strftime("%B %d, %Y"))

        category_icon = memory["category"].split('.')[-1].lower() if '.' in memory["category"] else memory["category"].lower()

        return {
            **memory,
            'date_str': date_str,
            'image_urls': [get_image_url(url) for url in memory.get('image_urls', [])],
            'caption': memory.get('caption', memory['description']),
            'category_icon': category_icon
        }

    def generate_html(self, profile: dict, memories: list, translations: dict) -> str:
        # Process memories
        memories.sort(key=lambda x: x['time_period'], reverse=False)
        formatted_memories = [self._format_memory_data(memory) for memory in memories]

        # Prepare template data
        template_data = {
            'frontend_url': self.frontend_url,
            'profile': profile,
            'memories': formatted_memories,
            'generation_date': datetime.now().strftime('%B %d, %Y'),
            'translations': translations
        }

        # Generate content sections
        title_content = self.env.get_template('title.html').render(**template_data)
        toc_content = self.env.get_template('toc.html').render(**template_data)
        memories_content = ''.join(
            self.env.get_template('memory.html').render(memory=memory, **template_data)
            for memory in formatted_memories
        )

        # Combine all sections
        content = title_content + toc_content + memories_content

        # Render final HTML
        return self.env.get_template('base.html').render(content=content, **template_data)

async def generate_PDF(template: str, sort_order: str, profile_id: str, language: str = 'en'):
    try:
        # Initialize services
        memory_service = MemoryService()
        doc_api = docraptor.DocApi()
        doc_api.api_client.configuration.username = os.getenv('DOCRAPTOR_API_KEY')

        # Load translations
        try:
            with open(f'i18n/{language}.json', 'r', encoding='utf-8') as f:
                translations = json.load(f)['pdf_generation']
        except Exception as e:
            logging.error(f"Error loading translations: {str(e)}")
            translations = {}

        # Get memories and profile data
        memories = await memory_service.get_memories_for_profile(profile_id)
        instance = MemoryService.get_instance()
        profile_result = instance.supabase.table("profiles")\
            .select("first_name,last_name")\
            .eq("id", profile_id)\
            .execute()

        if not profile_result.data:
            raise Exception("Profile not found")

        profile = profile_result.data[0]

        # Convert time_period strings to datetime objects
        for memory in memories:
            if isinstance(memory['time_period'], str):
                memory['time_period'] = datetime.fromisoformat(memory['time_period'].replace('Z', '+00:00'))

        # Sort memories
        if sort_order == 'category':
            memories.sort(key=lambda x: x['category'])
        else:
            memories.sort(key=lambda x: x['time_period'])

        # Generate HTML using templates
        pdf_generator = PDFGenerator()
        html_content = pdf_generator.generate_html(profile, memories, translations)

        # Generate PDF using DocRaptor
        try:
            response = doc_api.create_doc({
                'test': True,
                'document_type': 'pdf',
                'document_content': html_content,
                'name': f'memories_{profile_id}.pdf',
                'prince_options': {
                    'media': 'print',
                    'javascript': False,
                    'pdf_profile': 'PDF/A-1b'
                }
            })

            # Store and return PDF
            filename = f"{profile_id}/{uuid.uuid4()}.pdf"
            instance = MemoryService.get_instance()
            pdf_bytes = bytes(response)

            result = instance.supabase.storage.from_('pdfs').upload(
                path=filename,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf"}
            )

            signed_url = instance.supabase.storage.from_('pdfs').create_signed_url(
                path=filename,
                expires_in=86400
            )

            return signed_url['signedURL']

        except docraptor.rest.ApiException as error:
            logging.error(f"DocRaptor API error: Status {error.status}, Reason: {error.reason}")
            logging.error(f"Error body: {error.body}")
            raise Exception(f"PDF generation failed: {error.reason}")

    except Exception as e:
        logging.error(f"Error generating PDF: {str(e)}")
        raise

@router.post("/{profile_id}")
async def create_print_job(profile_id: str, request: PrintRequest):
    try:
        # Get user email from profile
        instance = MemoryService.get_instance()

        # First get profile data
        profile_result = instance.supabase.table("profiles")\
            .select("user_id")\
            .eq("id", profile_id)\
            .execute()

        if not profile_result.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        user_id = profile_result.data[0]['user_id']

        # Then get user email
        # Get user email using auth admin API
        try:
            supabase_client = create_client(
                supabase_url=os.getenv("SUPABASE_URL"),
                supabase_key=os.getenv("SUPABASE_KEY")
            )
            
            user_response = supabase_client.auth.admin.get_user_by_id(user_id)
            if not user_response or not user_response.user or not user_response.user.email:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no email")
            user_email = user_response.user.email
        except Exception as e:
            logging.error(f"Error getting user by ID: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get user details: {str(e)}")


        # Generate PDF and get download URL
        download_url = await generate_PDF(
            request.template,
            request.sortOrder,
            profile_id
        )

        # Send email using generic send_email function
        email_service = EmailService()
        await email_service.send_email(
            template_name='print-ready',
            to_email=user_email,
            subject_key='pdf_ready_subject',
            locale='en',  # You might want to get this from user preferences
            download_url=download_url
        )

        return {"message": "Print job submitted successfully"}

    except Exception as e:
        logging.error(f"Error in create_print_job: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create print job: {str(e)}"
        )