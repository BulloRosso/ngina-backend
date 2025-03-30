# /main.py
from fastapi import FastAPI, status , Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from api.v1 import router as v1_router
from api.v1.mcp import router as mcp_router
import logging
import os
from services.db_schema_creation import get_db_schema_service
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
import asyncio
from contextlib import asynccontextmanager

mcp = FastMCP("ngina-mpc-test-srv", port=5001, timeout=30)

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two integers and return sum.
    """
    return a + b 

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """
    Subtract two integers and return difference.
    """
    return a - b

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MCP server
    asyncio.create_task(mcp.run_sse_async())
    yield

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
    docs_url=None,  
    redoc_url=None, 
    lifespan=lifespan
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
        logging.StreamHandler()
    ]
)

logger  = logging.getLogger(__name__)
logger.info("Starting nginA API")

# POSTGRESQL (Supabase) connection via 
# TRANSACTION POOLER (6543)irect connection via pooler
db_user = os.getenv("PGUSER") 
db_password = os.getenv("PGPASSWORD")
db_host = os.getenv("PGHOST")
db_port = os.getenv("PGPORT")
db_name = os.getenv("PGDATABASE")

db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Initialize database schema service
db_schema_service = get_db_schema_service(db_url)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )
    
# Application startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    try:
        # Initialize database schema - default to 'app' schema if not specified
        schema_name = os.getenv("DB_SCHEMA", "test")
        db_schema_service.create_tables(schema_name)
        logger.info(f"Database tables initialized in schema '{schema_name}'")
    except Exception as e:
        logger.error(f"Error initializing database schema: {str(e)}")

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