# /main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import router as v1_router
from supabase import create_client
from dotenv import load_dotenv
import logging
import os

app = FastAPI(title="nginA API")

frontend_url = os.environ['FRONTEND_URL']

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", frontend_url,
                "https://ngina.replit.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/")
async def root():
   return {
       "status": "ready",
       "app": "nginA Backend",
       "version": "0.1.0"
   }
    
app.include_router(v1_router, prefix="/api")