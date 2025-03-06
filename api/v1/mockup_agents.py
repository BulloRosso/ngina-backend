# api/v1/mockup_agents.py
from fastapi import APIRouter, Response, HTTPException, Path, Request
from pydantic import BaseModel
from typing import Dict, Union, Any
from datetime import datetime
import json
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mockup-agents", tags=["mockup-agents"])

import uuid
from supabase import create_client

# Initialize Supabase client
supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

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

async def validate_wrapper_agent(agent_id: str):
    """
    Validate that the agent exists, is a wrapper, and return the agent data.
    """
    try:
        # Validate UUID format
        uuid_obj = uuid.UUID(agent_id)

        # Query Supabase for the agent
        result = supabase.table("agents")\
            .select("*")\
            .eq("id", str(uuid_obj))\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Agent not found")

        agent = result.data[0]

        # Check if this is a wrapper agent
        if not agent.get("agent_endpoint") or "wrapper" not in agent.get("agent_endpoint"):
            raise HTTPException(
                status_code=400, 
                detail="This agent is not a wrapper agent"
            )

        # Check if the wrapper has a workflow_id (target URL)
        if not agent.get("workflow_id"):
            raise HTTPException(
                status_code=400,
                detail="Wrapper agent doesn't have a target URL configured"
            )

        return agent
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        logger.error(f"Error validating wrapper agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to validate agent: {str(e)}")
        
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
            "icon_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M10,2V4.26L12,5.59V4H22V19H17V21H24V2H10M7.5,5L0,10V21H15V10L7.5,5M14,6V6.93L15.61,8H16V6H14M18,6V8H20V6H18M7.5,7.5L13,11V19H10V13H5V19H2V11L7.5,7.5M18,10V12H20V10H18M18,14V16H20V14H18Z" /></svg>',
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

async def get_crm_lookup_response():
    
    # Non-blocking wait for 3 to simulate AI processing
    await asyncio.sleep(3)

    return {
        "persons": [
            { "first_name": "John",
              "last_name": "Doe", 
              "email": "john.doe@house-junkies.com",
              "phone": "+49 123 456 789"
            }
        ]
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
                "image_xrl": "https://upload.wikimedia.org/wikipedia/commons/3/36/Durkin_Boarding_House_Park_City_Utah.jpeg"
             }
            },
            { "house": {
                "name": "Villa les hussards",
                "address": "In the center of the street 3, 8121 Belgere",
                "price": 1000500,
                "property_type": "Contemporary",
                "image_xrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Belgique_-_Rixensart_-_Villa_les_Hussards_-_01.jpg/1920px-Belgique_-_Rixensart_-_Villa_les_Hussards_-_01.jpg"
              }
            },
            { "house": {
                "name": "Villa Tugendhat",
                "address": "On the crest 4, 8121 Brno",
                "price": 370000,
                "property_type": "Contemporary",
                "image_xrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Vila_Tugendhat_Brno_2016_5.jpg/1920px-Vila_Tugendhat_Brno_2016_5.jpg"
              }
            },
            { "house": {
                "name": "Futuro Houses",
                "address": "In the middle of nowhere, 8121 Wanli",
                "price": 87700,
                "property_type": "Futuristic",
                "image_xrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Futuro_Village%2C_Wanli_10.jpg/1920px-Futuro_Village%2C_Wanli_10.jpg"
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
            "icon_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M13 19C13 18.66 13.04 18.33 13.09 18H4V8L12 13L20 8V13.09C20.72 13.21 21.39 13.46 22 13.81V6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H13.09C13.04 19.67 13 19.34 13 19M20 6L12 11L4 6H20M20 22V20H16V18H20V16L23 19L20 22Z" /></svg>',
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
        "success": True
    }

def get_personalized_writer_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "personalized_writer_agent",
            "title": {
                "de": "Immobilien-Poet",
                "en": "Real-estate Poetry Agent"
            },
            "description": {
                "de": "Beschreibt eine Immobilie in einem der gewählten Stile.",
                "en": "Describes a real estate property in one of the available Styles."
            },
            "icon_svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M8,12H16V14H8V12M10,20H6V4H13V9H18V12.1L20,10.1V8L14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H10V20M8,18H12.1L13,17.1V16H8V18M20.2,13C20.3,13 20.5,13.1 20.6,13.2L21.9,14.5C22.1,14.7 22.1,15.1 21.9,15.3L20.9,16.3L18.8,14.2L19.8,13.2C19.9,13.1 20,13 20.2,13M20.2,16.9L14.1,23H12V20.9L18.1,14.8L20.2,16.9Z" /></svg>',
            "maxRuntimeSeconds": 240
        },
        "credentials": {},
        "input": {
          "$schema": "http://json-schema.org/draft-04/schema#",
          "type": "object",
          "properties": {
            "style": {
              "type": "string",
              "description": "The artistic or emotional style to apply",
              "enum": ["simple", "romantic", "optimistic"]
            },
            "source_text": {
              "type": "string"
            },
            "max_words": {
              "type": "integer"
            }
          },
          "required": [
            "style",
            "source_text"
          ]
        },
        "output": {
          "$schema": "http://json-schema.org/draft-04/schema#",
          "type": "object",
          "properties": {
            "content": {
              "type": "string",
              "description": "The generated text in markdown format"
            }
          },
          "required": [
            "content"
          ]
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
            "icon_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M15.5,9C16.2,9 16.79,8.76 17.27,8.27C17.76,7.79 18,7.2 18,6.5C18,5.83 17.76,5.23 17.27,4.73C16.79,4.23 16.2,4 15.5,4C14.83,4 14.23,4.23 13.73,4.73C13.23,5.23 13,5.83 13,6.5C13,7.2 13.23,7.79 13.73,8.27C14.23,8.76 14.83,9 15.5,9M19.31,8.91L22.41,12L21,13.41L17.86,10.31C17.08,10.78 16.28,11 15.47,11C14.22,11 13.16,10.58 12.3,9.7C11.45,8.83 11,7.77 11,6.5C11,5.27 11.45,4.2 12.33,3.33C13.2,2.45 14.27,2 15.5,2C16.77,2 17.83,2.45 18.7,3.33C19.58,4.2 20,5.27 20,6.5C20,7.33 19.78,8.13 19.31,8.91M16.5,18H5.5L8.25,14.5L10.22,16.83L12.94,13.31L16.5,18M18,13L20,15V20C20,20.55 19.81,21 19.41,21.4C19,21.79 18.53,22 18,22H4C3.45,22 3,21.79 2.6,21.4C2.21,21 2,20.55 2,20V6C2,5.47 2.21,5 2.6,4.59C3,4.19 3.45,4 4,4H9.5C9.2,4.64 9.03,5.31 9,6H4V20H18V13Z" /></svg>',
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

def get_crm_lookup_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "crm_lookup",
            "title": {
                "de": "Customer Relationship Management System",
                "en": "Customer Relationship Management System"
            },
            "description": {
                "de": "Findet einen Kunden nach Name und Vorname.",
                "en": "Finds a customer by first name and surname."
            },
            "icon_svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M15.5,12C18,12 20,14 20,16.5C20,17.38 19.75,18.21 19.31,18.9L22.39,22L21,23.39L17.88,20.32C17.19,20.75 16.37,21 15.5,21C13,21 11,19 11,16.5C11,14 13,12 15.5,12M15.5,14A2.5,2.5 0 0,0 13,16.5A2.5,2.5 0 0,0 15.5,19A2.5,2.5 0 0,0 18,16.5A2.5,2.5 0 0,0 15.5,14M10,4A4,4 0 0,1 14,8C14,8.91 13.69,9.75 13.18,10.43C12.32,10.75 11.55,11.26 10.91,11.9L10,12A4,4 0 0,1 6,8A4,4 0 0,1 10,4M2,20V18C2,15.88 5.31,14.14 9.5,14C9.18,14.78 9,15.62 9,16.5C9,17.79 9.38,19 10,20H2Z" /></svg>',
            "maxRuntimeSeconds": 20
        },
        "credentials": {},
        "input": {
          "$schema": "http://json-schema.org/draft-04/schema#",
          "type": "object",
          "properties": {
            "first_name": {
              "type": "string"
            },
            "last_name": {
              "type": "string"
            }
          },
          "required": [
            "first_name",
            "last_name"
          ]
        },
        "output": {
            
              "$schema": "http://json-schema.org/draft-04/schema#",
              "type": "object",
              "properties": {
                "matching_persons": {
                  "type": "array",
                  "items": [
                    {
                      "type": "object",
                      "properties": {
                        "first_name": {
                          "type": "string"
                        },
                        "last_name": {
                          "type": "string"
                        },
                        "phone": {
                          "type": "string"
                        },
                        "email": {
                          "type": "string"
                        }
                      },
                      "required": [
                        "first_name",
                        "last_name",
                        "phone",
                        "email"
                      ]
                    }
                  ]
                }
              },
              "required": [
                "matching_persons"
              ]
            
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
            "icon_svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M7.03 4.95L3.5 8.5C.17 11.81 .17 17.19 3.5 20.5S12.19 23.83 15.5 20.5L21.5 14.5C22.5 13.53 22.5 11.94 21.5 10.96C21.4 10.84 21.27 10.73 21.13 10.64L21.5 10.25C22.5 9.28 22.5 7.69 21.5 6.71C21.36 6.55 21.17 6.41 21 6.3C21.38 5.38 21.21 4.28 20.46 3.53C19.59 2.66 18.24 2.57 17.26 3.25C17.16 3.1 17.05 2.96 16.92 2.83C15.95 1.86 14.36 1.86 13.38 2.83L10.87 5.34C10.78 5.2 10.67 5.07 10.55 4.95C9.58 4 8 4 7.03 4.95M8.44 6.37C8.64 6.17 8.95 6.17 9.15 6.37S9.35 6.88 9.15 7.08L5.97 10.26C7.14 11.43 7.14 13.33 5.97 14.5L7.38 15.91C8.83 14.46 9.2 12.34 8.5 10.55L14.8 4.25C15 4.05 15.31 4.05 15.5 4.25S15.71 4.76 15.5 4.96L10.91 9.56L12.32 10.97L18.33 4.96C18.53 4.76 18.84 4.76 19.04 4.96C19.24 5.16 19.24 5.47 19.04 5.67L13.03 11.68L14.44 13.09L19.39 8.14C19.59 7.94 19.9 7.94 20.1 8.14C20.3 8.34 20.3 8.65 20.1 8.85L14.44 14.5L15.85 15.92L19.39 12.38C19.59 12.18 19.9 12.18 20.1 12.38C20.3 12.58 20.3 12.89 20.1 13.09L14.1 19.1C11.56 21.64 7.45 21.64 4.91 19.1S2.37 12.45 4.91 9.91L8.44 6.37M23 17C23 20.31 20.31 23 17 23V21.5C19.5 21.5 21.5 19.5 21.5 17H23M1 7C1 3.69 3.69 1 7 1V2.5C4.5 2.5 2.5 4.5 2.5 7H1Z" /></svg>',
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

# ----------- crm lookup -------------------
@router.head("/crm-lookup")
async def head_crm_lookup_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/crm-lookup")
async def get_crm_lookup_metadata_endpoint():
    return get_crm_lookup_metadata()

@router.post("/crm-lookup")
async def post_crm_lookup_endpoint(request: Dict[str, Any]):
    return await get_crm_lookup_response()

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

# --------- web scaper ----------
def get_web_page_scraper_metadata():
    return {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": "web_page_scraper_agent",
            "title": {
                "de": "Web Scraper",
                "en": "Web Scraper"
            },
            "description": {
                "de": "Extrahiert den Inhalt als Markdown aus der übergebenen öffentlichen web url. Es wird nur https: als Protokoll unterstützt",
                "en": "Extracts content as markdown from the provided public web URL. Only https: protocol is supported"
            },
            "icon_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M16.36,14C16.44,13.34 16.5,12.68 16.5,12C16.5,11.32 16.44,10.66 16.36,10H19.74C19.9,10.64 20,11.31 20,12C20,12.69 19.9,13.36 19.74,14M14.59,19.56C15.19,18.45 15.65,17.25 15.97,16H18.92C17.96,17.65 16.43,18.93 14.59,19.56M14.34,14H9.66C9.56,13.34 9.5,12.68 9.5,12C9.5,11.32 9.56,10.65 9.66,10H14.34C14.43,10.65 14.5,11.32 14.5,12C14.5,12.68 14.43,13.34 14.34,14M12,19.96C11.17,18.76 10.5,17.43 10.09,16H13.91C13.5,17.43 12.83,18.76 12,19.96M8,8H5.08C6.03,6.34 7.57,5.06 9.4,4.44C8.8,5.55 8.35,6.75 8,8M5.08,16H8C8.35,17.25 8.8,18.45 9.4,19.56C7.57,18.93 6.03,17.65 5.08,16M4.26,14C4.1,13.36 4,12.69 4,12C4,11.31 4.1,10.64 4.26,10H7.64C7.56,10.66 7.5,11.32 7.5,12C7.5,12.68 7.56,13.34 7.64,14M12,4.03C12.83,5.23 13.5,6.57 13.91,8H10.09C10.5,6.57 11.17,5.23 12,4.03M18.92,8H15.97C15.65,6.75 15.19,5.55 14.59,4.44C16.43,5.07 17.96,6.34 18.92,8M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z" /></svg>',
            "maxRuntimeSeconds": 60
        },
        "credentials": {},
        "input": {
            "url_to_scrape": {"type": "text", "description": "The public web URL to scrape (https: protocol only)"}
        },
        "output": {
            "markdown": {"type": "text", "description": "The extracted content in markdown format"},
            "success": {"type": "boolean", "description": "TRUE if successful, FALSE if there was an error"},
            "error_message": {"type": "text", "description": "Error message in case of failure"}
        }
    }

async def get_web_page_scraper_response(request):
    import httpx
    import asyncio
    from urllib.parse import urlparse

    # Extract the URL from the request
    url_to_scrape = request.get("url_to_scrape")
    logger.info("Scraping url " + url_to_scrape)
    
    # Validate URL (basic validation)
    parsed_url = urlparse(url_to_scrape)
    if not parsed_url.scheme or parsed_url.scheme != "https":
        return {
            "markdown": "",
            "success": False,
            "error_message": "Only https: protocol is supported"
        }

    try:
        # Create the scraping URL by appending to the base URL
        scrape_url = f"https://r.jina.ai/{url_to_scrape}"

        # Perform the web request with a timeout
        async with httpx.AsyncClient() as client:
            response = await client.get(scrape_url, timeout=5.0)

            if response.status_code == 200:
                # Return the content as markdown
                return {
                    "markdown": response.text,
                    "success": True,
                    "error_message": ""
                }
            else:
                return {
                    "markdown": "",
                    "success": False,
                    "error_message": f"Failed to scrape URL. Status code: {response.status_code}"
                }

    except httpx.TimeoutException:
        return {
            "markdown": "",
            "success": False,
            "error_message": "Request timed out after 5 seconds"
        }
    except Exception as e:
        return {
            "markdown": "",
            "success": False,
            "error_message": f"An error occurred: {str(e)}"
        }

# Add these endpoints to your router definition in the main file:

@router.head("/web-page-scraper")
async def head_web_page_scraper_endpoint():
    return Response(headers={"x-alive": "true"})

@router.get("/web-page-scraper")
async def get_web_page_scraper_metadata_endpoint():
    return get_web_page_scraper_metadata()

@router.post("/web-page-scraper")
async def post_web_page_scraper_endpoint(request: Dict[str, Any]):
    return await get_web_page_scraper_response(request)

@router.head("/wrapper/{agent_id}")
async def head_wrapper_endpoint(agent_id: str = Path(...)):
    """
    HEAD request handler for wrapper agents.
    Validates the agent exists and is a wrapper.
    """
    # Validate agent
    await validate_wrapper_agent(agent_id)

    # Return alive header
    return Response(headers={"x-alive": "true"})

@router.get("/wrapper/{agent_id}")
async def get_wrapper_metadata_endpoint(agent_id: str = Path(...)):
    """
    GET request handler for wrapper agents.
    Returns the agent metadata in the ngina-metadata.0.9 format.
    """
    # Validate and get agent data
    agent = await validate_wrapper_agent(agent_id)

    # Create the metadata response from the agent data
    metadata_response = {
        "schemaName": "ngina-metadata.0.9",
        "metadata": {
            "name": agent.get("id"),
            "title": agent.get("title", {"en": "Wrapped Agent", "de": "Wrapped Agent"}),
            "description": agent.get("description", {"en": "", "de": ""}),
            "icon_svg": agent.get("icon_svg", ""),
            "maxRuntimeSeconds": agent.get("max_execution_time_secs", 30)
        },
        "credentials": {},
        "input": agent.get("input", {}),
        "output": agent.get("output", {})
    }

    return metadata_response

@router.post("/wrapper/{agent_id}")
async def post_wrapper_endpoint(request: Request, agent_id: str = Path(...)):
    """
    POST request handler for wrapper agents.
    Acts as a proxy to the target URL (workflow_id).
    """
    import httpx

    # Validate and get agent data
    agent = await validate_wrapper_agent(agent_id)

    # Get the target URL from workflow_id
    target_url = agent.get("workflow_id")

    # Get request body
    request_body = await request.json()

    # Prepare headers based on authentication
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Handle authentication if configured
    auth = agent.get("authentication", "none")
    if auth != "none":
        if auth.startswith("header:"):
            # Custom header authentication
            header_name = auth.replace("header:", "")
            # Expect the header value to be in the credentials
            if "credentials" in request_body and header_name in request_body["credentials"]:
                headers[header_name] = request_body["credentials"][header_name]
            else:
                # For testing, we'll allow the request to proceed without the credential
                logger.warning(f"Custom header {header_name} required but not provided")

        elif auth.startswith("basic-auth:"):
            # Basic authentication
            auth_parts = auth.replace("basic-auth:", "").split(",")
            if len(auth_parts) == 2:
                username, password = auth_parts
                # Create auth
                import base64
                auth_string = f"{username}:{password}"
                auth_bytes = auth_string.encode('ascii')
                base64_bytes = base64.b64encode(auth_bytes)
                base64_auth = base64_bytes.decode('ascii')
                headers["Authorization"] = f"Basic {base64_auth}"

        elif auth == "bearer-token":
            # Bearer token authentication
            if "credentials" in request_body and "token" in request_body["credentials"]:
                headers["Authorization"] = f"Bearer {request_body['credentials']['token']}"
            else:
                # For testing, we'll allow the request to proceed without the credential
                logger.warning("Bearer token required but not provided")

    try:
        # Make the request to the target URL
        logger.info(f"Proxying request to {target_url}")
        logger.debug(f"Request body: {request_body}")

        timeout = agent.get("max_execution_time_secs", 30)

        async with httpx.AsyncClient() as client:
            # Remove credentials from the request if any
            if "credentials" in request_body:
                del request_body["credentials"]

            # Forward the request
            response = await client.post(
                target_url, 
                json=request_body,
                headers=headers,
                timeout=float(timeout)
            )

            # Return the exact response from the target, regardless of status code
            try:
                # Try to parse as JSON first
                return response.json()
            except:
                # If it's not JSON, return the text content
                return Response(
                    content=response.text,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "text/plain")
                )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"Request to target agent timed out after {timeout} seconds"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with target agent: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in wrapper proxy: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )