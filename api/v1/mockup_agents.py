# api/v1/mockup_agents.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Union, Optional
from datetime import datetime
import json

router = APIRouter(prefix="/mockup-agents", tags=["mockup-agents"])

class AgentMetadata(BaseModel):
    name: str
    title: Dict[str, str]
    description: Dict[str, str]
    maxRuntimeSeconds: int

class MetadataResponse(BaseModel):
    schemaName: str = "ngina-metadata.0.9"
    metadata: AgentMetadata
    credentials: Dict = {}
    input: Dict
    output: Dict

class AgentInvocation(BaseModel):
    schemaName: str = "ngina-agentinvocation.0.9"
    credentials: Dict = {}
    input: Dict[str, Union[str, int, float, datetime, Dict]]
    callbackUrl: str

def get_real_estate_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "real_estate_db_agent",
            "title": {
                "de": "Immobilien-Datenbank Agent",
                "en": "Real Estate Database Agent"
            },
            "description": {
                "de": "Verwaltet Immobilien-Datenbank Anfragen",
                "en": "Manages real estate database queries"
            },
            "maxRuntimeSeconds": 180
        },
        "credentials": {},
        "input": {
            "region": {"type": "text"},
            "price_range": {"type": "text"},
            "property_type": {"type": "text"}
        },
        "output": {
            "name": {"type": "text"},
            "address": {"type": "text"},
            "price": {"type": "number"},
            "property_type": {"type": "text"},
            "region": {"type": "text"},
            "image_url": {"type": "text"}
        }
    }

def get_html_email_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "html_email_agent",
            "title": {
                "de": "HTML Email Generator",
                "en": "HTML Email Generator"
            },
            "description": {
                "de": "Erstellt HTML-formatierte Emails",
                "en": "Creates HTML-formatted emails"
            },
            "maxRuntimeSeconds": 120
        },
        "credentials": {},
        "input": {
            "template": {"type": "text"},
            "content": {"type": "text"},
            "style": {"type": "text"}
        },
        "output": {
            "html_content": {"type": "text/html"}
        }
    }

def get_personalized_writer_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "personalized_writer_agent",
            "title": {
                "de": "Personalisierter Schreibassistent",
                "en": "Personalized Writing Assistant"
            },
            "description": {
                "de": "Erstellt personalisierte Texte",
                "en": "Creates personalized text content"
            },
            "maxRuntimeSeconds": 240
        },
        "credentials": {},
        "input": {
            "topic": {"type": "text"},
            "style": {"type": "text"},
            "length": {"type": "number"}
        },
        "output": {
            "content": {"type": "text"}
        }
    }

def get_image_selector_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "image_selector_agent",
            "title": {
                "de": "Bildauswahl Agent",
                "en": "Image Selection Agent"
            },
            "description": {
                "de": "Wählt passende Bilder aus einer Sammlung",
                "en": "Selects appropriate images from a collection"
            },
            "maxRuntimeSeconds": 150
        },
        "credentials": {},
        "input": {
            "category": {"type": "text"},
            "style": {"type": "text"},
            "count": {"type": "number"}
        },
        "output": {
            "images": {"type": "array", "items": {"type": "file", "subtype": "image/jpeg"}}
        }
    }

@router.get("/real-estate-db")
async def get_real_estate_metadata_endpoint():
    return get_real_estate_metadata()

@router.post("/real-estate-db")
async def post_real_estate_endpoint(request: AgentInvocation):
    return {"message": "What a beautiful day!"}

@router.get("/html-email")
async def get_html_email_metadata_endpoint():
    return get_html_email_metadata()

@router.post("/html-email")
async def post_html_email_endpoint(request: AgentInvocation):
    return {"message": "What a beautiful day!"}

@router.get("/personalized-writer")
async def get_personalized_writer_metadata_endpoint():
    return get_personalized_writer_metadata()

@router.post("/personalized-writer")
async def post_personalized_writer_endpoint(request: AgentInvocation):
    return {"message": "What a beautiful day!"}

@router.get("/image-selector")
async def get_image_selector_metadata_endpoint():
    return get_image_selector_metadata()

@router.post("/image-selector")
async def post_image_selector_endpoint(request: AgentInvocation):
    return {"message": "What a beautiful day!"}