# services/knowledgemanagement.py
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging
from uuid import UUID
from models.memory import (
    Category, 
    Memory, 
    Location, 
    MemoryCreate, 
    Person,
    Emotion
)
from services.memory import MemoryService
import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
import os
import asyncio
import time

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class MemoryClassification(BaseModel):
    """Model for classified memory information"""
    is_memory: bool
    rewritten_text: str
    category: Optional[str]
    location: Optional[str]
    timestamp: str  # ISO format date string

class KnowledgeManagement:
    """Class for managing knowledge management"""
    def __init__(self):
        self.memory_service = MemoryService()
    
    # In services/knowledgemanagement.py
    @staticmethod
    async def analyze_response(
        response_text: str, 
        client, 
        profile_data: dict,
        language: str = "en",
        narrator_perspective: str = "ego",
        narrator_style: str = "neutral",
        narrator_verbosity: str = "normal"
    ) -> MemoryClassification:
        """Analyze user response to classify and enhance memory content with profile settings"""
        try:
            # Use profile information
            pronoun = "him" if profile_data["gender"].lower() == "male" else "her"
            profile_context = f"The main character of our memories is {profile_data['first_name']} {profile_data['last_name']} which is of {profile_data['gender']} gender. When rewriting memories reference to {pronoun} as {profile_data['first_name']}."

            # Convert perspective setting to prompt text
            perspective_text = "in first person view" if narrator_perspective == "ego" else "in third person view"

            # Convert style setting to prompt text
            style_text = {
                "professional": "using a clear and professional tone",
                "romantic": "using a warm and emotional tone",
                "optimistic": "using a positive and uplifting tone",
                "neutral": "using a balanced and neutral tone"
            }.get(narrator_style, "using a neutral tone")

            # Convert verbosity setting to prompt text
            verbosity_text = {
                "verbose": "more detailed and elaborate",
                "normal": "similar in length",
                "brief": "more concise and focused"
            }.get(narrator_verbosity, "similar in length")

            # Set temperature based on style
            temperature = {
                "professional": 0.1,
                "neutral": 0.3
            }.get(narrator_style, 0.7)

            # Build the prompt
            prompt = f"""Analyze the following text and classify it as a memory or not. 

            {profile_context}
             
            If it is a memory, rewrite it {perspective_text}, {style_text}. Also extract the category, location, and timestamp.
            Compared to the user's input, your rewritten text should be {verbosity_text}.
            If the exact date is unknown, please estimate the month and year based on context clues
            or use the current date if no time information is available.

            IMPORTANT: Keep the response in the original language ({language}).

            Text: {response_text}

            Return result as JSON with the following format:
            {{
                "is_memory": true/false,
                "rewritten_text": "rewritten memory in {language}",
                "category": "one of: childhood, career, travel, relationships, hobbies, pets",
                "location": "where it happened or 'Unknown' if not mentioned",
                "timestamp": "YYYY-MM-DD (if unknown, use current date)"
            }}
            """

            logger.debug(f"Using temperature {temperature} for style {narrator_style}")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a memory analysis assistant that responds in {language}. Keep the rewritten text in the original language."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=temperature
            )

            result = response.choices[0].message.content
            classification = MemoryClassification.parse_raw(result)

            # Set default current date if timestamp is invalid
            if classification.timestamp in ["unbekannt", "unknown", ""]:
                classification.timestamp = datetime.now().strftime("%Y-%m-%d")

            classification.timestamp = classification.timestamp.replace("-XX", "-01")

            logger.info(f"Memory classification complete: {classification}")
            return classification

        except Exception as e:
            logger.error(f"Error analyzing response: {str(e)}")
            raise

    async def store_memory(self, profile_id: UUID, session_id: UUID, classification: MemoryClassification) -> Optional[Memory]:
        """
        Store classified memory in both Supabase and Neo4j (future implementation)
        """
        try:
            if not classification.is_memory:
                logger.debug("Text classified as non-memory, skipping storage")
                return None
            
            # Parse timestamp or use current date if invalid
            try:
                timestamp = datetime.fromisoformat(classification.timestamp)
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp '{classification.timestamp}', using current date")
                timestamp = datetime.now()
                
            # Prepare memory data
            memory_data = {
                "category": classification.category or Category.CHILDHOOD.value,
                "description": classification.rewritten_text,
                "time_period": datetime.fromisoformat(classification.timestamp),
                "location": {
                    "name": classification.location if classification.location != "unbekannt" else "Unknown",
                    "city": None,
                    "country": None,
                    "description": None
                } if classification.location else None,
                "people": [],
                "emotions": [],
                "image_urls": [],
                "audio_url": None
            }

            # Store in Supabase
            stored_memory = await MemoryService.create_memory(
                MemoryCreate(**memory_data),
                profile_id,
                session_id
            )

            # in the background: store in Neo4j knowledge graph (vector and graph search)
            asyncio.create_task(self.append_to_rag(classification.rewritten_text, classification.category, classification.location))

            logger.info(f"Memory stored successfully")
            return stored_memory

        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}")
            raise
            
    async def append_to_rag(self, memory_text, category, location):

        neo4j_driver = neo4j.GraphDatabase.driver(NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

        ex_llm=LLM(
        model_name="gpt-4o-mini",
        model_params={
        "response_format": {"type": "json_object"},
        "temperature": 0
        })

        embedder = Embeddings()

        prompt_for_noblivion = '''
        You are a knowledge manager and you task is extracting information from life memories of people 
        and structuring it in a property graph to inform further research and Q&A.

        Extract the entities (nodes) and specify their type from the following Input text.
        Also extract the relationships between these nodes. the relationship direction goes from the start node to the end node. 

        Return result as JSON using the following format:
        {{"nodes": [ {{"id": "0", "label": "the type of entity", "properties": {{"name": "name of entity" }} }}],
        "relationships": [{{"type": "TYPE_OF_RELATIONSHIP", "start_node_id": "0", "end_node_id": "1", "properties": {{"details": "Description of the relationship"}} }}] }}

        - Use only the information from the Input text. Do not add any additional information.  
        - If the input text is empty, return empty Json. 
        - Make sure to create as many nodes and relationships as needed to offer rich medical context for further research.
        - An AI knowledge assistant must be able to read this graph and immediately understand the context to inform detailed research questions. 
        - Multiple documents will be ingested from different sources and we are using this property graph to connect information, so make sure entity types are fairly general. 

        Use only fhe following nodes and relationships (if provided):
        --------------------

        --------------------

        Assign a unique ID (string) to each node, and reuse it to define relationships.
        Do respect the source and target node types for relationship and
        the relationship direction.

        Do not return any additional information other than the JSON in it.

        Examples:
        {examples}

        Input text:

        {text}
        '''

        """
        class SimpleKGPipelineConfig(BaseModel):
        llm: LLMInterface
        driver: neo4j.Driver
        from_pdf: bool
        embedder: Embedder
        entities: list[SchemaEntity] = Field(default_factory=list)
        relations: list[SchemaRelation] = Field(default_factory=list)
        potential_schema: list[tuple[str, str, str]] = Field(default_factory=list)
        pdf_loader: Any = None
        kg_writer: Any = None
        text_splitter: Any = None
        on_error: OnError = OnError.RAISE
        prompt_template: Union[ERExtractionTemplate, str] = ERExtractionTemplate()
        perform_entity_resolution: bool = True
        lexical_graph_config: Optional[LexicalGraphConfig] = None
        neo4j_database: Optional[str] = None

        model_config = ConfigDict(arbitrary_types_allowed=True)
        """

        entities_noblivion = [
        "Person",
        "City",
        "Country",
        "Job",
        "Organization",
        "Pet",
        "MedicalCondition",
        "MedicalProcedure",
        "Car",
        "House",
        "Book",
        "Movie",
        "Series"
        ]

        relations_noblivion = [
        "TRAVELED_TO",
        "FIRST_MET",
        "BOUGHT",
        "WATCHED",
        "HAS_READ",
        "IS_FRIEND_OF",
        "SOLD",
        "WORKED_AT",
        "LIKED",
        "HATED",
        "LIVED_IN",
        "HAPPENED_IN"
        ]
        
        # Build KG and Store in Neo4j Database
        kg_builder_txt = SimpleKGPipeline(
             llm=ex_llm,
             driver=neo4j_driver,
             embedder=embedder,
             relations=relations_noblivion,
             entities=entities_noblivion,
             text_splitter=FixedSizeSplitter(chunk_size=2000, chunk_overlap=500),
             prompt_template=prompt_for_noblivion,
             from_pdf=False
        )
        logger.info("...Executing RAG pipeline")
        start_time = time.time()
        await kg_builder_txt.run_async(text=f'{memory_text} category {category} location {location}') 
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"...> RAG pipeline execution time: {execution_time} seconds")
        
        return ""

    async def query_with_rag(self, query_text: str) -> str:
        """
        Query the knowledge graph using RAG and return the answer.
        """
        try:
            logger.info("Initializing GraphRAG for query")
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
            rag = GraphRAG(llm=llm, retriever=hybrid_retriever)
    
            # Get response
            logger.debug(f"Executing RAG query: {query_text}")
            response = rag.search(query_text=query_text)
            logger.debug(f"Generated response: {response.answer}")
    
            return response.answer
    
        except Exception as e:
            logger.error(f"Error processing RAG query: {str(e)}")
            raise Exception(f"Failed to process RAG query: {str(e)}")