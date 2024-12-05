# api/v1/memories.py
from fastapi import APIRouter, UploadFile, File, Form
from typing import List
from uuid import UUID
from models.memory import Memory, MemoryCreate
from services.pdfgenerator import PDFGenerator

from dotenv import load_dotenv
import os

router = APIRouter(prefix="/memories", tags=["memories"])

@router.post("/")
async def create_memory(
    memory: MemoryCreate,
    profile_id: UUID,
    session_id: UUID
):
    return await Memory.create(memory, profile_id, session_id)

@router.get("/{profile_id}")
async def get_memories(profile_id: UUID):
    return await Memory.get_by_profile(profile_id)

@router.post("/{memory_id}/media")
async def upload_media(
    memory_id: UUID,
    files: List[UploadFile] = File(...)
):
    return await Memory.add_media(memory_id, files)

@router.delete("/{memory_id}")
async def delete_memory(memory_id: UUID):
    return await Memory.delete(memory_id)

@router.post("/export-pdf")
async def export_memories_pdf():
    try:
        # Get all memories from Neo4j
        with GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            "neo4j", 
            os.getenv("NEO4J_PWD")
        ) as driver:
            with driver.session() as session:
                memories = session.run("""
                    MATCH (m:Memory)
                    OPTIONAL MATCH (m)-[:INVOLVES]->(p:Person)
                    OPTIONAL MATCH (m)-[:OCCURRED_AT]->(l:Location)
                    OPTIONAL MATCH (m)-[:EVOKED]->(e:Emotion)
                    RETURN m, 
                           collect(distinct p) as people,
                           collect(distinct l) as locations,
                           collect(distinct e.type) as emotions
                    ORDER BY m.time_period
                """).data()

        pdf_generator = PDFGenerator(supabase_client)
        result = await pdf_generator.generate_memory_pdf(memories)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))