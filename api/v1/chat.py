# api/v1/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.generation.graphrag import GraphRAG
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatQuery(BaseModel):
    profile_id: UUID
    query_text: str

class ChatResponse(BaseModel):
    answer: str

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def get_graph_rag():
    try:
        neo4j_driver = neo4j.GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

        embedder = Embeddings()

        hybrid_retriever = HybridRetriever(
            neo4j_driver,
            fulltext_index_name="fulltext_index_noblivion",
            vector_index_name="vector_index_noblivion",
            embedder=embedder
        )

        llm = LLM(model_name="gpt-4o-mini")
        return GraphRAG(llm=llm, retriever=hybrid_retriever)
    except Exception as e:
        logger.error(f"Error initializing GraphRAG: {str(e)}")
        raise

@router.post("", response_model=ChatResponse)
async def process_chat_message(query: ChatQuery):
    try:
        logger.info(f"Processing chat message for profile {query.profile_id}")
        logger.debug(f"Query text: {query.query_text}")

        # Initialize GraphRAG
        rag = await get_graph_rag()

        # Get response
        response = rag.search(query_text=query.query_text)

        logger.debug(f"Generated response: {response.answer}")
        return ChatResponse(answer=response.answer)

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )