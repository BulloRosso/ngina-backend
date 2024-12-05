from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1 import router as v1_router
from supabase import create_client
from dotenv import load_dotenv
import os

app = FastAPI(title="Noblivion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
       "app": "Noblivion Backend",
       "version": "1.0.0"
   }
    
app.include_router(v1_router, prefix="/api")