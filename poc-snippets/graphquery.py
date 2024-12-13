# Test for neo 4j
import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
import os
import asyncio

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def graphrag():

  neo4j_driver = neo4j.GraphDatabase.driver(NEO4J_URI,
                                            auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
  
  ex_llm=LLM(
     model_name="gpt-4o-mini",
     model_params={
         "response_format": {"type": "json_object"},
         "temperature": 0
     })
  
  embedder = Embeddings()

  # 2. Hybrid Retriever
  hybrid_retriever = HybridRetriever(
     neo4j_driver,
     fulltext_index_name="fulltext_index_noblivion",
     vector_index_name="vector_index_noblivion",
     embedder=embedder
  )
  
  # 3. GraphRAG Class
  llm = LLM(model_name="gpt-4o-mini")
  rag = GraphRAG(llm=llm, retriever=hybrid_retriever)
  
  # 4. Run
  response = rag.search(query_text="Welche Personen lernte Horst Winkler in Spanien kennen?")
  print(response.answer)

print("Starting neo4j graph query:")
asyncio.run(graphrag())
