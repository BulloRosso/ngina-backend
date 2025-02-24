# api/v1/mockup_agents.py
from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Dict, Union, Any
from datetime import datetime
import json
import asyncio

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
            "region": "Mandatory parameter. Region, z.B. 'Berlin'",
            "min_price": 100000,
            "property_type": "Optional parameter. Building style as one of the classes 'Contemporary', 'Classic' or 'Medieval'"
        },
        "output": {
          "$schema": "http://json-schema.org/schema#",
          "type": "object",
          "properties": {
            "results": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "house": {
                    "type": "object",
                    "properties": {
                      "name": {
                        "type": "string",
                        "description": "the name of the house in English"
                      },
                      "address": {
                        "type": "string",
                        "description": "street name and number, zip code city name"
                      },
                      "price": {
                        "type": "integer",
                        "description": "520000"
                      },
                      "property_type": {
                        "type": "string",
                        "description": "one of the enum values 'a', 'b' or 'c'"
                      },
                      "image_url": {
                        "type": "string",
                        "description": "a public url of a image in png or jpg format. **must not** require authentication"
                      }
                    },
                    "required": [
                      "address",
                      "image_url",
                      "name",
                      "price",
                      "property_type"
                    ]
                  }
                },
                "required": [
                  "house"
                ]
              }
            }
          },
          "required": [
            "results"
          ]
        }
    }

async def get_real_estate_response():

    # Non-blocking wait for 3 to simulate AI processing
    await asyncio.sleep(3)
    
    return {
        "results": [
             { "house": {
                "name": "Hollyhill House",
                "address": "In the middle of the street 3, 8121 Ulbucerque",
                "price": 520000,
                "property_type": "Classic",
                "image_url": "https://commons.wikimedia.org/wiki/Category:Boarding_houses#/media/File:Durkin_Boarding_House_Park_City_Utah.jpeg"
             }
            },
            { "house": {
                "name": "Villa les hussards",
                "address": "In the center of the street 3, 8121 Belgere",
                "price": 1000500,
                "property_type": "Contemporary",
                "image_url": "https://commons.wikimedia.org/wiki/Category:Modernist_houses_in_Belgium#/media/File:Belgique_-_Rixensart_-_Villa_les_Hussards_-_01.jpg"
              }
            },
            { "house": {
                "name": "Villa Tugendhat",
                "address": "On the crest 4, 8121 Brno",
                "price": 370000,
                "property_type": "Contemporary",
                "image_url": "https://commons.wikimedia.org/wiki/Category:Villa_Tugendhat#/media/File:Vila_Tugendhat_Brno_2016_5.jpg"
              }
            },
            { "house": {
                "name": "Futuro Houses",
                "address": "In the middle of nowhere, 8121 Wanli",
                "price": 87700,
                "property_type": "Futuristic",
                "image_url": "https://commons.wikimedia.org/wiki/Category:Futuro#/media/File:Futuro_Village,_Wanli_10.jpg"
              }
            }
        ]
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
            "recipients": {"type": "array",
                          "description": "An string array of email addresses"},
            "template": {"type": "text", 
                         "description": "Mandatory parameter. Available templates are 'business', 'romantic' or 'family'."},
            "content": {"type": "text",
                         "description": "Mandatory parameter. The textual content of the email in markdown format."},
            "style": {"type": "text",
                         "description": "Optional Parameter. Available styles are 'colorful' or 'calm'"}
        },
        "output": {
            "success": {"type": "boolean", 
                        "description": "TRUE is success, FALSE is failure"},
            "error": {"type": "text", 
                      "description": "error message in case of failure"}
        }
    }

async def get_html_email_response():

    # Non-blocking wait for 3 to simulate AI processing
    await asyncio.sleep(3)
    
    return {
        "success": true
    }

def get_personalized_writer_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "personalized_writer_agent",
            "title": {
                "de": "Beschreibt ein Bild.",
                "en": "Describes an image."
            },
            "description": {
                "de": "Erstellt personalisierte Texte",
                "en": "Creates personalized text content"
            },
            "maxRuntimeSeconds": 240
        },
        "credentials": {},
        "input": {
            "topic": {"type": "text",
                     "description": "Mandatory parameter. Name of the object to descirbe, e.g. 'My cute poodle Cookie'"},
            "img_url": {"type": "url",
                      "description": "Mandatory parameter. The public url of an jpg or png image to be analyzed" },
            "max_length": {"type": "number",
                          "description": "Optional parameter. Maximum length of the generated text in words. Default is 500"}
        },
        "output": {
            "content": {"type": "text",
                       "description": "The text which was created as description of the image provided as input."}
        }
    }

async def get_personalized_writer_response():
    
    # Non-blocking wait for 3 to simulate AI processing
    await asyncio.sleep(3)
    
    return  {
        "content": "This is the description for the selected house. In demo mode this is not very interesting to read."
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

def get_discover_me_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "discover_me_agent",
            "title": {
                "de": "Discovery Beispiel Agent",
                "en": "Discovery Example Agent"
            },
            "description": {
                "de": "Verwenden Sie diesen Agenten, um die Discovery-Funktion zu testen.",
                "en": "Use this agent to test the Discovery function."
            },
            "maxRuntimeSeconds": 20
        },
        "credentials": {},
        "input": {
            "category": {"type": "text", "description": "Kategorie, die gesucht werden soll"},
            "style": {"type": "text", "description": "Stil, die gesucht werden soll"},
            "count": {"type": "number", "description": "Anzahl der Ergebnisse, die geliefert werden sollen"}
        },
        "output": {
            "images": {"type": "array", "description": "Ergebnisse, die geliefert werden sollen" }
        }
    }

# ---------- real estate db lookup  ----------

@router.head("/real-estate-db")
async def head_real_estate_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/real-estate-db")
async def get_real_estate_metadata_endpoint():
    return get_real_estate_metadata()

@router.post("/real-estate-db")
async def post_real_estate_endpoint(request: Dict[str, Any]):
    return await get_real_estate_response()

# --------- send email demo service ----------------------

@router.head("/html-email")
async def head_html_email_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/html-email")
async def get_html_email_metadata_endpoint():
    return get_html_email_metadata()

@router.post("/html-email")
async def post_html_email_endpoint(request: Dict[str, Any]):
    return await get_html_email_response()

# --------- personalized writer demo service ----------------------

@router.head("/personalized-writer")
async def head_personalized_writer_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/personalized-writer")
async def get_personalized_writer_metadata_endpoint():
    return get_personalized_writer_metadata()

@router.post("/personalized-writer")
async def post_personalized_writer_endpoint(request: Dict[str, Any]):
    return await get_personalized_writer_response()

# --------- image selector demo service ----------------------

@router.head("/image-selector")
async def head_image_selector_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/image-selector")
async def get_image_selector_metadata_endpoint():
    return get_image_selector_metadata()

@router.post("/image-selector")
async def post_image_selector_endpoint(request: Dict[str, Any]):
    return request

# --------- discover me demo service ----------------------

@router.head("/discover-me")
async def head_discover_me_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/discover-me")
async def get_discover_me_metadata_endpoint():
    return get_discover_me_metadata()

@router.post("/discover-me")
async def post_discover_me_endpoint(request: Dict[str, Any]):
    return request