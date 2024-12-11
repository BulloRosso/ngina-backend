# /main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import router as v1_router
from supabase import create_client
from dotenv import load_dotenv
import logging
import os
import logging


logger = logging.getLogger()  # Root logger
logger.setLevel(logging.INFO)  # Set the logging level

# Create a file handler
file_handler = logging.FileHandler("agent.log")
file_handler.setLevel(logging.INFO)  # Set level for this handler
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

# Create a stream handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Set level for this handler
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("This is an INFO log.")
logger.debug("This is a DEBUG log.")

app = FastAPI(title="Noblivion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://8ede5a9c-1536-4919-b14f-82f6fd92faca-00-bvc5u3f2ay1d.janeway.replit.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)
"""
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        logger.debug(f"Request path: {request.url.path}")
        logger.debug(f"Request method: {request.method}")
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        # Log the error message and stack trace
        logger.error(f"An error occurred while processing the request: {e}", exc_info=True)
        raise  # Re-raise the exception to let FastAPI handle it properly
"""

# Initialize Supabase client
supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

@app.get("/")
async def root():
   return {
       "status": "ready",
       "app": "Noblivion Backend",
       "version": "1.0.0"
   }
    
app.include_router(v1_router, prefix="/api")