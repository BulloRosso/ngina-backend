# /main.py
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from api.v1 import router as v1_router
from supabase import create_client
from dotenv import load_dotenv
import logging
import os

# Custom OpenAPI metadata
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="nginA API",
        version="0.1.0",
        description="API for the nginA application",
        routes=app.routes,
    )

    # You can customize the schema further here if needed
    # For example, adding security schemes
    # openapi_schema["components"]["securitySchemes"] = {...}

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Initialize FastAPI with metadata
app = FastAPI(
    title="nginA API",
    version="0.1.0",
    description="API for the nginA application",
    docs_url=None,  # Disable default docs URL
    redoc_url=None  # Disable default redoc URL
)

# Set custom OpenAPI schema function
app.openapi = custom_openapi

# CORS middleware configuration
frontend_url = os.environ['FRONTEND_URL']

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        frontend_url,
        "https://*.replit.dev",
        "https://ngina.replit.app"],
    allow_origin_regex=r"https://.*\.replit\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

# Initialize Supabase client
supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
   return RedirectResponse(url="/api/redoc")
    
# OpenAPI Schema JSON endpoint
@app.get("/api/openapi.json", include_in_schema=False)
async def get_openapi_json():
    return app.openapi()
    
# Custom docs endpoints
@app.get("/api/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="nginA API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/api/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="nginA API Documentation - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

app.include_router(v1_router, prefix="/api")