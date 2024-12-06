from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import router as v1_router
from supabase import create_client
from dotenv import load_dotenv
import logging
import os

app = FastAPI(title="Noblivion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://8ede5a9c-1536-4919-b14f-82f6fd92faca-00-bvc5u3f2ay1d.janeway.replit.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#    logger.debug(f"Request path: {request.url.path}")
#    logger.debug(f"Request method: {request.method}")
#    response = await call_next(request)
#    logger.debug(f"Response status: {response.status_code}")
#    return response

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