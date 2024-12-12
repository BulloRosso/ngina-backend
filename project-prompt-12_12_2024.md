# Noblivion - Your experiences are precious
Noblivion is a AI system which helps you capturing your personal or professional experiences during various on-screen interviews. The empathetic AI interviewer guides you through the depths of your memories, captures them, gives them structure and finally ouputs them as a book in PDF format.

## How to get Noblivion?
Noblivion is a gift from children to their parents and the process starts when a person enters the personal data of another person (called the client from here) as profile in the Noblivion React frontend. This profile contains personal information and will help the AI interviewer to get started and to focus on the most relevant facets of the client.

## Process of the interviews
An interview can only start if a profileID (UUIDv4) is selected in the frontend. Then we change to the memory collection process:
* first initiate a new sessionID 
* every client input or ai output will be collected in a session object in the storage
* create an message to the client using AI giving some ideas what memories could be collected in this session
* receive on input item from the client which could be eiter text input multiline, audio recording from direct voice input, uploaded image file or image taken from the camera
* binary input items should be saved in object storage, text items should be stored directly in the session object, audio should be transcribed using openAI API and converted and saved as text item
* the backend extracts information for the knowledge graph using OpenAI entity extraction and appends the information (like relationships to persons, likes and dislikes of the client)
* the backend extracts timeline information using an OpenAI prompts and extends the timeline object with a reference to the input item (so the frontend can later display a link to the memory)
* the backend extracts the sentiment of the current user input by taking the last 4 user inputs as a reference and sends it back to the frontend (the frontend displays it as an icon)
* the backend constructs a reflection on the users input item with OpenAI and sends it back to the frontend (the frontend displays it and reads it as audio produced by a streaming OpenAI text synthesis call)
* the next input item is received until the user presses an "Leave/end interview session" in the frontend

## Capturing of memories of the client 
We want to capture and extract the following data from the interviews and arrange them in a structure.

For each memory which is received from the frontend by the backend it has to be analyzed in the following steps:

1. extract the point in time from the memory text using AI. If no point in time was found use today as timestamp.
2. store the memory with the point in time as formated text or as image resource
3. extract named entities and relationships from the memory text using AI
4. update the knowledge graph with named entities and relationships
5. query the knowledge graph with the first named entity to get information for the follow up question

### timeline
Each memory is assigned to a point in time and and optional location (e. g. "I met Kerstin on 22.02.1971 in Nürnberg, Germany")
### memory
The memory as a formatted text using markdown and optional images
### knowledge graph
The knowledge graph contains all relations between persons, locations, pets, houses/addresses and other entities which happened in the life of the client

We will implement the knowledge graph using neo4j-graphrag library:
```python
pip install fsspec langchain-text-splitters tiktoken openai python-dotenv numpy torch neo4j-graphrag
```

This is an example how to use the neo4j-graphrag Python library:
```python
from dotenv import load_dotenv
import os

# load neo4j credentials (and openai api key in background).
load_dotenv('.env', override=True)
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')


import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.generation.graphrag import GraphRAG

neo4j_driver = neo4j.GraphDatabase.driver(NEO4J_URI,
                                          auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

ex_llm=LLM(
   model_name="gpt-4o-mini",
   model_params={
       "response_format": {"type": "json_object"},
       "temperature": 0
   })

embedder = Embeddings()

# 1. Build KG and Store in Neo4j Database
kg_builder_pdf = SimpleKGPipeline(
   llm=ex_llm,
   driver=neo4j_driver,
   embedder=embedder,
   from_pdf=True
)
await kg_builder_pdf.run_async(file_path='precision-med-for-lupus.pdf')

# 2. KG Retriever
vector_retriever = VectorRetriever(
   neo4j_driver,
   index_name="text_embeddings",
   embedder=embedder
)

# 3. GraphRAG Class
llm = LLM(model_name="gpt-4o")
rag = GraphRAG(llm=llm, retriever=vector_retriever)

# 4. Run
response = rag.search( "How is precision medicine applied to Lupus?")
print(response.answer)
```
The SimpleKGPipeline class allows you to automatically build a knowledge graph with a few key inputs, including
* a driver to connect to Neo4j,
* an LLM for entity extraction, and
* an embedding model to create vectors on text chunks for similarity search.

Likewise, we will use OpenAI’s default **text-embedding-3-small** for the embedding model.

In the graph DB we will use a schema, which can be used in the potential_schema argument:
```
category_node_labels = ["childhood", "career", "travel", "travel","hobbies", "pets"]

location_node_labels = ["Home", "Workplace"]

node_labels = basic_node_labels + category_node_labels + location_node_labels

# define relationship types
rel_types = ["MET", "TRAVELED", "IS_CHILD_OF", "BOUGHT", "SOLD", …]
```
While not required, adding a graph schema is highly recommended for improving knowledge graph quality. It provides guidance for the node and relationship types to create during entity extraction.

For our graph schema, we will define entities (a.k.a. node labels) and relations that we want to extract. While we won’t use it in this simple example, there is also an optional potential_schema argument, which can guide which relationships should connect to which nodes.

We can use fill the nodes in neo4j using the matching prompt:
```
prompt_template = '''
You are an empathetic interviewer which extracts information from answers of the client 
and structuring it in a property graph to document the life of the client.

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
{schema}

Assign a unique ID (string) to each node, and reuse it to define relationships.
Do respect the source and target node types for relationship and
the relationship direction.

Do not return any additional information other than the JSON in it.

Examples:
{examples}

Input text:

{text}
'''
```

We won't use PDFs as input like in the examples here - we will use the plain text of the memories.
```
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

kg_builder_pdf = SimpleKGPipeline(
   llm=ex_llm,
   driver=driver,
   text_splitter=FixedSizeSplitter(chunk_size=500, chunk_overlap=100),
   embedder=embedder,
   entities=node_labels,
   relations=rel_types,
   prompt_template=prompt_template,
   from_pdf=True
)
```
A Note on Custom & Detailed Knowledge Graph Building
Under the Hood, the SimpleKGPipeline runs the components listed below. The GraphRAG package provides a lower-level pipeline API, allowing you to customize the knowledge graph-building process to a great degree. For further details, see this documentation.

* Document Parser: extract text from documents, such as PDFs.
* Text Splitter: split text into smaller pieces manageable by the LLM context window (token limit).
* Chunk Embedder: compute the text embeddings for each chunk
* Schema Builder: provide a schema to ground the LLM entity extraction for an accurate and easily navigable knowledge graph.
* Entity & Relation Extractor: extract relevant entities and relations from the text
* Knowledge Graph Writer: save the identified entities and relations to the KG

2. Retrieve Data From Your Knowledge Graph
The GraphRAG Python package provides multiple classes for retrieving data from your knowledge graph, including:

* Vector Retriever: performs similarity searches using vector embeddings
* Vector Cypher Retriever: combines vector search with retrieval queries in Cypher, Neo4j’s Graph Query language, to traverse the graph and incorporate additional nodes and relationships.
* Hybrid Retriever: Combines vector and full-text search.
* Hybrid Cypher Retriever: Combines vector and full-text search with Cypher retrieval queries for additional graph traversal.
* Text2Cypher: converts natural language queries into Cypher queries to run against Neo4j.
* Weaviate & Pinecone Neo4j Retriever: Allows you to search vectors stored in Weaviate or Pinecone and connect them to nodes in Neo4j using external id properties.
* Custom Retriever: allows for tailored retrieval methods based on specific needs.
* These retrievers enable you to implement diverse data retrieval patterns, boosting the relevance and accuracy of your RAG pipelines.

#####Instantiate and Run GraphRAG
The GraphRAG Python package makes instantiating and running GraphRAG pipelines easy. We can use a dedicated GraphRAG class. At a minimum, you need to pass the constructor an LLM and a retriever. You can optionally pass a custom prompt template. We will do so here, just to provide a bit more guidance for the LLM to stick to information from our data source.

Below we create GraphRAG objects for both the vector and vector-cypher retrievers.
```
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG

llm = LLM(model_name="gpt-4o",  model_params={"temperature": 0.0})

rag_template = RagTemplate(template='''Answer the Question using the following Context. Only respond with information mentioned in the Context. Do not inject any speculative information not mentioned.

# Question:
{query_text}

# Context:
{context}

# Answer:
''', expected_inputs=['query_text', 'context'])

v_rag  = GraphRAG(llm=llm, retriever=vector_retriever, prompt_template=rag_template)
vc_rag = GraphRAG(llm=llm, retriever=vc_retriever, prompt_template=rag_template)
```
Now we can ask a simple question and see how the different knowledge graph retrieval patterns compare:
```
q = "How is precision medicine applied to Lupus? provide in list format."

print(f"Vector Response: \n{v_rag.search(q, retriever_config={'top_k':5}).answer}")
print("\n===========================\n")
print(f"Vector + Cypher Response: \n{vc_rag.search(q, retriever_config={'top_k':5}).answer}")
```
Of course, one can tune and combine retrieval methods to further improve these responses; this is just a starting example. Let’s ask a bit more complex questions that require sourcing information from multiple text chunks.
```
q = "Can you summarize systemic lupus erythematosus (SLE)? including common effects, biomarkers, and treatments? Provide in detailed list format."

v_rag_result = v_rag.search(q, retriever_config={'top_k': 5}, return_context=True)
vc_rag_result = vc_rag.search(q, retriever_config={'top_k': 5}, return_context=True)

print(f"Vector Response: \n{v_rag_result.answer}")
print("\n===========================\n")
print(f"Vector + Cypher Response: \n{vc_rag_result.answer}")
```

## Processing pipeline for a client's answer
After the backend received an answer it follows these steps in sequence:
1. Analyze whether the text is a memory or not using the current answer and the memory buffer content for this session using an LLM call
2. IF the text is not a memory just return an answer
3. IF the text is a memory then try to extract the category and and rewrite the client's answer to in warm and confident tone using the frontend's current language
4. Come up with the follow-up answer and return it immediatelly to the client
5. Store the memory into Supabase
6. Inform the frontend to refresh the memory timeline
7. Add the memory to GraphRAG in neo4j
8. Add the question and the answer to a memory buffer for this session

## Technical parts of the Noblivion system

### Frontend: React, vite, mui v6 and Typescript
The frontend uses plaing mui v6 styling and is intended to used by non-trained users. Handling instructions and step-by-step guidance should always be provided.

#### App (entry point)
The app looks like this:
-------------------
{frontend_entrypoint}
-------------------

These are the libraries used by the app. Always prefer using an existing library/package to solve a problem rather than adding a new one:
--------------------
{frontend_packages}
--------------------

#### Components
These are the components we already have. You can modify them if you like:
--------------------
{frontend_components}
---------------------

### Services
These are the exitsing frontend services:
--------------
{frontend_services}
--------------

#### Types
These are the types which we use. They must be always in sync with the Python models in the Backend. If you want to add something always change the Python model
first and then the type definition in the frontend project:
------------------------
{frontend_types}
------------------------

#### Primary colors
When we use colors then prefer:
* Blue #1eb3b7
* Green #879b15
* Orange #fc9c2b
* Red #ee391c

#### Multi-language setup/i18n
You should not insert labels as plain text but always use the react-i18n-library:
---------------------
{frontend_i18n}
---------------------

### Backend: Python, FastAPI and Pydantic, neo4j knowledge graph
The backend exposes several API endpoints. Internally it uses models to maintain models.
These are the models:
----------------------

### models/memory.py
```
# models/memory.py
from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
from uuid import UUID, uuid4

class Category(str, Enum):
    CHILDHOOD = "childhood"
    CAREER = "career"
    TRAVEL = "travel"
    RELATIONSHIPS = "relationships"
    HOBBIES = "hobbies"
    PETS = "pets"

    @classmethod
    def _missing_(cls, value):
        """Handle case when enum value has 'Category.' prefix"""
        if isinstance(value, str):
            # Remove 'Category.' prefix if it exists
            clean_value = value.replace('Category.', '').lower()
            for member in cls:
                if member.value.lower() == clean_value:
                    return member
        return None

class Person(BaseModel):
    name: str
    relation: str
    age_at_time: Optional[int]

class Location(BaseModel):
    name: str
    city: Optional[str]
    country: Optional[str]
    description: Optional[str]

class Emotion(BaseModel):
    type: str
    intensity: float
    description: Optional[str]

class MemoryCreate(BaseModel):
    category: Category
    description: str
    time_period: datetime
    location: Optional[Location]
    people: List[Person] = []
    emotions: List[Emotion] = []
    image_urls: List[str] = []
    audio_url: Optional[str]

class MemoryUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    time_period: Optional[datetime] = None
    location: Optional[dict] = None
    people: Optional[List[dict]] = None
    emotions: Optional[List[dict]] = None
    image_urls: Optional[List[str]] = None
    audio_url: Optional[str] = None

class Memory(MemoryCreate):
    id: UUID4
    profile_id: UUID4
    session_id: UUID4
    created_at: datetime
    updated_at: datetime
    sentiment_analysis: Optional[Dict]

class InterviewResponse(BaseModel):
    text: str
    language: str
    audio_url: Optional[str] = None
    emotions_detected: Optional[List[Emotion]] = None
    session_id: Optional[UUID] = None  

class InterviewQuestion(BaseModel):
    text: str
    context: Optional[str]
    suggested_topics: List[str] = []
    requires_media: bool = False
```

### models/profile.py
```
# models/profile.py
from pydantic import BaseModel, UUID4, EmailStr
from datetime import date, datetime
from typing import List, Optional

class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    gender: str
    children: List[str] = []
    spoken_languages: List[str] = []
    profile_image_url: Optional[str]

class Profile(ProfileCreate):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

class Achievement(BaseModel):
    id: str
    type: str
    title: dict  # Multilingual
    description: dict  # Multilingual
    icon: str
    color: str
    required_count: int
    unlocked_at: Optional[datetime]

class AchievementProgress(BaseModel):
    profile_id: UUID4
    achievement_id: str
    current_count: int
    completed: bool
    unlocked_at: Optional[datetime]
```
----------------------
These are the endpoints:
----------------------

### api/v1/__init__.py
```
# api/v1/__init__.py
from fastapi import APIRouter
from .interviews import router as interviews_router
from .memories import router as memories_router
from .achievements import router as achievements_router
from .profiles import router as profiles_router

router = APIRouter(prefix="/v1")
router.include_router(interviews_router)
router.include_router(memories_router)
router.include_router(achievements_router)
router.include_router(profiles_router)
```

### api/v1/achievements.py
```
# api/v1/achievements.py
from fastapi import APIRouter
from uuid import UUID
from services.achievements import AchievementService

router = APIRouter(prefix="/achievements", tags=["achievements"])

@router.get("/{profile_id}")
async def get_achievements(profile_id: UUID, language: str = 'en'):
    service = AchievementService()
    return await service.get_profile_achievements(profile_id, language)

@router.post("/check")
async def check_achievements(profile_id: UUID):
    service = AchievementService()
    unlocked = await service.check_achievements(profile_id)
    return {"unlocked_achievements": unlocked}
```

### api/v1/interviews.py
```
# api/v1/interviews.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from uuid import UUID
from services.sentiment import EmpatheticInterviewer
from models.memory import InterviewResponse, InterviewQuestion
import logging
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

@router.post("/{profile_id}/start")
async def start_interview(profile_id: UUID, language: str = "en"):
    interviewer = EmpatheticInterviewer()
    return await interviewer.start_new_session(profile_id, language)

@router.post("/{profile_id}/response")
async def process_response(
    profile_id: UUID,
    response: InterviewResponse,
    session_id: UUID = Query(...)  # Now it comes after the required arguments
):
    """Process a response from the interview."""
    try:
        interviewer = EmpatheticInterviewer()
        return await interviewer.process_interview_response(
            profile_id=profile_id,
            session_id=session_id,
            response_text=response.text,
            language=response.language
        )
    except Exception as e:
        logger.error(f"Error processing response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process response: {str(e)}"
        )

@router.get("/{profile_id}/question")
async def get_next_question(
    profile_id: UUID,
    session_id: UUID,
    language: str = "en"
):
    """Get the next interview question based on the session context."""
    try:
        interviewer = EmpatheticInterviewer()
        result = await interviewer.generate_next_question(profile_id, session_id, language)
        return {
            "text": result,
            "suggested_topics": [],
            "requires_media": False
        }
    except Exception as e:
        logger.error(f"Error generating next question: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate next question"
        )
```

### api/v1/memories.py
```
# api/v1/memories.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from typing import List
from uuid import UUID
from models.memory import Memory, MemoryCreate, MemoryUpdate
from services.memory import MemoryService
import logging
import traceback
from pydantic import BaseModel
from datetime import datetime
import io

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

@router.put("/{memory_id}")
async def update_memory(memory_id: UUID, memory: MemoryUpdate):
    """Update a memory by ID"""
    try:
        logger.debug(f"Received update request for memory_id={memory_id}")
        logger.debug(f"Update data: {memory.dict(exclude_unset=True)}")

        # Only include fields that were actually provided in the update
        update_data = memory.dict(exclude_unset=True)

        # Ensure category is properly formatted if provided
        if 'category' in update_data and isinstance(update_data['category'], str):
            update_data['category'] = update_data['category'].replace('Category.', '')

        # Convert time_period to ISO format if provided
        if 'time_period' in update_data and isinstance(update_data['time_period'], datetime):
            update_data['time_period'] = update_data['time_period'].isoformat()

        result = await MemoryService.update_memory(memory_id, update_data)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Memory not found"
            )

        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating memory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update memory: {str(e)}"
        )

@router.get("/{profile_id}")
async def get_memories_by_profile(profile_id: UUID) -> List[Memory]:
    """Get all memories for a specific profile"""
    try:
        logger.debug(f"Fetching memories for profile_id={profile_id}")

        memory_service = MemoryService.get_instance()
        result = memory_service.supabase.table("memories").select("*").eq(
            "profile_id", str(profile_id)
        ).order('created_at', desc=True).execute()

        if not result.data:
            return []

        # Convert string category to enum value
        memories = []
        for memory_data in result.data:
            # Remove 'Category.' prefix if it exists
            if isinstance(memory_data.get('category'), str):
                memory_data['category'] = memory_data['category'].replace('Category.', '')
            try:
                memories.append(Memory(**memory_data))
            except Exception as e:
                logger.error(f"Error converting memory data: {str(e)}")
                logger.error(f"Problematic memory data: {memory_data}")
                continue

        return memories

    except Exception as e:
        logger.error(f"Error fetching memories: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch memories: {str(e)}"
        )
        
@router.post("")
async def create_memory(
    request: Request,
    memory: MemoryCreate,
    profile_id: UUID,
    session_id: UUID
):
    try:
        logger.debug(f"Received create memory request for profile_id={profile_id}, session_id={session_id}")
        logger.debug(f"Memory data: {memory.dict()}")

        # Verify the session exists first
        session_exists = await MemoryService.verify_session(session_id, profile_id)
        if not session_exists:
            logger.warning(f"Session not found: profile_id={profile_id}, session_id={session_id}")
            raise HTTPException(
                status_code=404,
                detail="Interview session not found or doesn't belong to this profile"
            )

        # Log the request body for debugging
        body = await request.json()
        logger.debug(f"Request body: {body}")

        result = await MemoryService.create_memory(memory, profile_id, session_id)
        logger.debug(f"Memory created successfully: {result}")
        return result
    except HTTPException as he:
        logger.error(f"HTTP Exception: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Error creating memory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error creating memory: {str(e)}"
        )

@router.delete("/{memory_id}")
async def delete_memory(memory_id: UUID):
    """Delete a memory by ID"""
    try:
        logger.debug(f"Received delete request for memory_id={memory_id}")

        deleted = await MemoryService.delete_memory(memory_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Memory not found"
            )

        return {"status": "success", "message": "Memory deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting memory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete memory: {str(e)}"
        )

@router.delete("/{memory_id}/media/{filename}")
async def delete_media_from_memory(memory_id: UUID, filename: str):
    """Delete a media file from a memory"""
    try:
        logger.debug(f"Deleting media {filename} from memory {memory_id}")

        result = await MemoryService.delete_media_from_memory(memory_id, filename)

        return {"success": True, "message": "Media deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete media: {str(e)}"
        )
        
@router.post("/{memory_id}/media")
async def add_media_to_memory(
    memory_id: UUID,
    files: List[UploadFile] = File(...),
):
    """Add media files to a memory"""
    try:
        logger.debug(f"Received media upload request for memory_id={memory_id}")
        logger.debug(f"Number of files: {len(files)}")

        # Read and validate each file
        file_contents = []
        content_types = []

        for file in files:
            content_type = file.content_type
            if not content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not an image"
                )

            content = await file.read()
            file_contents.append(content)
            content_types.append(content_type)

        # Process the files
        result = await MemoryService.add_media_to_memory(
            memory_id=memory_id,
            files=file_contents,
            content_types=content_types
        )

        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error adding media: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add media: {str(e)}"
        )
```

### api/v1/profiles.py
```
# api/v1/profiles.py
from fastapi import APIRouter, HTTPException, File, Form, Request, UploadFile
from typing import Optional
from uuid import UUID
import json
import os
from datetime import datetime, date
import traceback
from models.profile import Profile, ProfileCreate
from supabase import create_client
import asyncio
from services.profile import ProfileService
from io import BytesIO
from typing import List
from models.profile import Profile
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"])

# Initialize Supabase client
supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

@router.get("")
async def list_profiles() -> List[Profile]:
    """Get all profiles"""
    try:
        profiles = await ProfileService.get_all_profiles()
        return profiles
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch profiles: {str(e)}")
            
@router.post("")
async def create_profile(
  profile_image: UploadFile = File(...),
  profile: str = Form(...)
):
  try:
      profile_data = json.loads(profile)
      # print("Profile data before creation:", profile_data)  # Debug print
      first_name = profile_data.get("first_name")
      last_name = profile_data.get("last_name")
      profile_data["date_of_birth"] = datetime.strptime(profile_data["date_of_birth"], "%Y-%m-%d").date()

      if not first_name or not last_name:
          raise ValueError("Both first_name and last_name are required.")

      file_path = f"profile_images/{first_name}_{last_name}.jpg"
      file_content = await profile_image.read()
      
      try:
          supabase.storage.from_("profile-images").remove([file_path])
      except:
          pass

      result = supabase.storage.from_("profile-images").upload(
          path=file_path,
          file=file_content,
          file_options={"content-type": profile_image.content_type}
      )

      image_url = supabase.storage.from_("profile-images").get_public_url(file_path)
      profile_data["profile_image_url"] = image_url

      profile_create = ProfileCreate(**profile_data)
      return await ProfileService.create_profile(profile_create)

  except Exception as e:
      tb = traceback.extract_tb(e.__traceback__)[-1]
      error_info = f"Error in {tb.filename}, line {tb.lineno}: {str(e)}"
      print(f"Validation error: {error_info}")
      raise HTTPException(
          status_code=500, 
          detail=f"Error processing profile: {error_info}"
      )

@router.get("/{profile_id}")
async def get_profile(profile_id: UUID):
    """Get a profile by ID"""
    try:
        logger.debug(f"Fetching profile with ID: {profile_id}")
        service = ProfileService()  # Create instance
        profile = await service.get_profile(profile_id)  # Call instance method

        if not profile:
            logger.debug(f"Profile not found: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found")

        return profile
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
```
----------------------
When you change existing endpoints give a clear notice.

These are the exitsing backend services:
--------------

### services/__init__.py
```
# services/__init__.py
from .interviewer import MemoryInterviewer
from .sentiment import EmpatheticInterviewer
from .achievements import AchievementService
from .pdfgenerator import PDFGenerator
```

### services/achievements.py
```
# services/achievements.py
from typing import List
from uuid import UUID
from datetime import datetime
from models.profile import Achievement, AchievementProgress

class AchievementService:
    async def check_achievements(self, profile_id: UUID) -> List[Achievement]:
        try:
            stats = await self._get_profile_stats(profile_id)
            current_achievements = await self._get_current_achievements(profile_id)
            unlocked = []

            for achievement in self.ACHIEVEMENTS:
                if achievement.id not in current_achievements and \
                   await self._check_achievement_criteria(achievement, stats):
                    await self._unlock_achievement(profile_id, achievement.id)
                    unlocked.append(achievement)

            return unlocked
        except Exception as e:
            raise ValueError(f"Achievement check failed: {str(e)}")

    async def get_profile_achievements(
        self,
        profile_id: UUID,
        language: str = 'en'
    ) -> List[dict]:
        try:
            achievements = await self._get_all_achievements()
            progress = await self._get_achievement_progress(profile_id)

            return [
                {
                    **achievement.dict(),
                    'title': achievement.title[language],
                    'description': achievement.description[language],
                    'progress': progress.get(achievement.id, 0)
                }
                for achievement in achievements
            ]
        except Exception as e:
            raise ValueError(f"Failed to get achievements: {str(e)}")

    # Helper methods to be implemented
    async def _get_profile_stats(self, profile_id: UUID):
        pass

    async def _get_current_achievements(self, profile_id: UUID):
        pass

    async def _check_achievement_criteria(self, achievement: Achievement, stats: dict):
        pass

    async def _unlock_achievement(self, profile_id: UUID, achievement_id: str):
        pass
```

### services/memory.py
```
# services/memory.py
from typing import Optional, List
from uuid import UUID
from models.memory import MemoryCreate
from supabase import create_client, Client
import os
from datetime import datetime
import logging
import traceback
import io
from PIL import Image
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryService:
    table_name = "memories"
    storage_bucket = "memory-media"
    
    def __init__(self):
        logger.debug("Initializing MemoryService")
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
    @classmethod
    async def delete_memory(cls, memory_id: UUID) -> bool:
        """Delete a memory by ID"""
        try:
            logger.debug(f"Attempting to delete memory with ID: {memory_id}")
            instance = cls.get_instance()

            # Delete the memory from Supabase
            result = instance.supabase.table(cls.table_name).delete().eq(
                "id", str(memory_id)
            ).execute()

            logger.debug(f"Delete response: {result}")

            # Check if deletion was successful
            if not result.data:
                logger.warning(f"No memory found with ID {memory_id}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error deleting memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to delete memory: {str(e)}")

    @classmethod
    async def update_memory(cls, memory_id: UUID, memory_data: dict) -> bool:
        """Update a memory by ID"""
        try:
            logger.debug(f"Attempting to update memory with ID: {memory_id}")
            logger.debug(f"Update data: {memory_data}")

            instance = cls.get_instance()

            # Handle time_period field name conversion
            if "time_period" in memory_data:
                time_period = memory_data["time_period"]
                # Ensure it's in ISO format if it's not already
                if isinstance(time_period, datetime):
                    time_period = time_period.isoformat()
                memory_data["time_period"] = time_period

            # Add updated_at timestamp
            update_data = {
                **memory_data,
                "updated_at": datetime.utcnow().isoformat()
            }

            # Update the memory in Supabase
            result = instance.supabase.table(cls.table_name)\
                .update(update_data)\
                .eq("id", str(memory_id))\
                .execute()

            logger.debug(f"Update response: {result}")

            # Check if update was successful
            if not result.data:
                logger.warning(f"No memory found with ID {memory_id}")
                return False

            return result.data[0]

        except Exception as e:
            logger.error(f"Error updating memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to update memory: {str(e)}")
            
    @staticmethod
    def get_instance():
        if not hasattr(MemoryService, "_instance"):
            MemoryService._instance = MemoryService()
        return MemoryService._instance

    @classmethod
    async def verify_session(cls, session_id: UUID, profile_id: UUID) -> bool:
        """Verify that the session exists and belongs to the profile"""
        try:
            logger.debug(f"Verifying session for profile_id={profile_id}, session_id={session_id}")
            instance = cls.get_instance()
            result = instance.supabase.table("interview_sessions").select("*").eq(
                "id", str(session_id)
            ).eq(
                "profile_id", str(profile_id)
            ).execute()

            session_exists = len(result.data) > 0
            logger.debug(f"Session verification result: {session_exists}")
            return session_exists
        except Exception as e:
            logger.error(f"Error verifying session: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    @classmethod
    async def create_memory(cls, memory: MemoryCreate, profile_id: UUID, session_id: UUID):
        """Create a new memory"""
        try:
            logger.debug(f"Creating memory for profile_id={profile_id}, session_id={session_id}")
            logger.debug(f"Memory data: {memory.dict()}")

            instance = cls.get_instance()
            now = datetime.utcnow().isoformat()

            # Log the memory object to see what we're working with
            logger.debug(f"Memory object: {memory}")

            # Create the data dictionary with full error handling
            try:
                data = {
                    "profile_id": str(profile_id),
                    "session_id": str(session_id),
                    "category": str(memory.category),
                    "description": str(memory.description),
                    "time_period": datetime.now().isoformat(),  # Use current time if time_period is causing issues
                    "emotions": [],  # Start with empty arrays if these are causing issues
                    "people": [],
                    "image_urls": [],
                    "created_at": now,
                    "updated_at": now
                }

                # Add optional fields with validation
                if hasattr(memory, 'location') and memory.location:
                    data["location"] = memory.location.dict() if hasattr(memory.location, 'dict') else None

                if hasattr(memory, 'emotions') and memory.emotions:
                    data["emotions"] = [emotion.dict() for emotion in memory.emotions] if all(hasattr(e, 'dict') for e in memory.emotions) else []

                if hasattr(memory, 'people') and memory.people:
                    data["people"] = [person.dict() for person in memory.people] if all(hasattr(p, 'dict') for p in memory.people) else []

                if hasattr(memory, 'image_urls') and memory.image_urls:
                    data["image_urls"] = memory.image_urls

                if hasattr(memory, 'audio_url') and memory.audio_url:
                    data["audio_url"] = memory.audio_url

                logger.debug(f"Prepared data for insert: {data}")
            except Exception as e:
                logger.error(f"Error preparing memory data: {str(e)}")
                logger.error(traceback.format_exc())
                raise Exception(f"Error preparing memory data: {str(e)}")

            # Insert into database with error logging
            try:
                response = instance.supabase.table(cls.table_name).insert(data).execute()
                logger.debug(f"Supabase response: {response}")

                if not response.data:
                    raise Exception("No data returned from memory creation")

                return response.data[0]
            except Exception as e:
                logger.error(f"Error inserting into database: {str(e)}")
                logger.error(traceback.format_exc())
                raise

        except Exception as e:
            logger.error(f"Error in create_memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to create memory: {str(e)}")

    @classmethod
    async def delete_media_from_memory(cls, memory_id: UUID, filename: str) -> bool:
        """Delete a media file from storage and update the memory record"""
        try:
            logger.debug(f"Deleting media {filename} from memory {memory_id}")
            instance = cls.get_instance()

            # First, get the current memory record to get the image URLs
            memory = instance.supabase.table(cls.table_name)\
                .select("image_urls")\
                .eq("id", str(memory_id))\
                .execute()

            if not memory.data:
                raise Exception("Memory not found")

            # Get current image URLs
            current_urls = memory.data[0].get('image_urls', [])

            # Generate the storage URL that matches our stored URL pattern
            storage_url = instance.supabase.storage\
                .from_(cls.storage_bucket)\
                .get_public_url(f"{memory_id}/{filename}")

            # Find and remove the URL from the list
            updated_urls = [url for url in current_urls if url != storage_url]

            if len(updated_urls) == len(current_urls):
                logger.warning(f"URL not found in memory record: {storage_url}")

            # Delete from storage
            try:
                delete_result = instance.supabase.storage\
                    .from_(cls.storage_bucket)\
                    .remove([f"{memory_id}/{filename}"])

                logger.debug(f"Storage delete result: {delete_result}")
            except Exception as e:
                logger.error(f"Error deleting from storage: {str(e)}")
                # Continue anyway to update the memory record
                pass

            # Update the memory record with the new URL list
            update_result = instance.supabase.table(cls.table_name)\
                .update({"image_urls": updated_urls})\
                .eq("id", str(memory_id))\
                .execute()

            logger.debug(f"Memory update result: {update_result}")

            return True

        except Exception as e:
            logger.error(f"Error deleting media from memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to delete media: {str(e)}")
    
    @classmethod
    async def add_media_to_memory(cls, memory_id: UUID, files: List[bytes], content_types: List[str]) -> dict:
        """Add media files to a memory and return the URLs"""
        try:
            logger.debug(f"Adding media to memory {memory_id}")
            instance = cls.get_instance()

            # Verify memory exists
            memory = instance.supabase.table(cls.table_name)\
                .select("image_urls")\
                .eq("id", str(memory_id))\
                .execute()

            if not memory.data:
                raise Exception("Memory not found")

            current_urls = memory.data[0].get('image_urls', [])
            new_urls = []

            for idx, (file_content, content_type) in enumerate(zip(files, content_types)):
                try:
                    # Generate unique filename
                    file_ext = "jpg" if "jpeg" in content_type.lower() else "png"
                    filename = f"{memory_id}/{uuid.uuid4()}.{file_ext}"

                    # Upload to Supabase Storage
                    result = instance.supabase.storage\
                        .from_(cls.storage_bucket)\
                        .upload(
                            path=filename,
                            file=file_content,
                            file_options={"content-type": content_type}
                        )

                    if hasattr(result, 'error') and result.error:
                        raise Exception(f"Upload error: {result.error}")

                    # Get public URL
                    url = instance.supabase.storage\
                        .from_(cls.storage_bucket)\
                        .get_public_url(filename)

                    new_urls.append(url)

                except Exception as e:
                    logger.error(f"Error uploading file {idx}: {str(e)}")
                    continue

            # Update memory with new URLs
            updated_urls = current_urls + new_urls
            update_result = instance.supabase.table(cls.table_name)\
                .update({"image_urls": updated_urls})\
                .eq("id", str(memory_id))\
                .execute()

            return {
                "message": "Media added successfully",
                "urls": new_urls,
                "total_urls": len(updated_urls)
            }

        except Exception as e:
            logger.error(f"Error adding media: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to add media: {str(e)}")
```

### services/sentiment.py
```
# services/sentiment.py
from uuid import UUID, uuid4
from datetime import datetime
from models.memory import InterviewQuestion
import openai
import os
from typing import Dict, Any
from supabase import create_client, Client
import logging
from services.knowledgemanagement import KnowledgeManagement, MemoryClassification

logger = logging.getLogger(__name__)

class EmpatheticInterviewer:
    def __init__(self):
        self.openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.knowledge_manager = KnowledgeManagement()

    async def start_new_session(self, profile_id: UUID, language: str = "en") -> Dict[str, Any]:
        """Start a new interview session for a profile."""
        try:
            # Generate an empathetic opening question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an empathetic interviewer helping people preserve their memories. 
                        Generate a warm, inviting opening question that encourages sharing personal memories.
                        Respond in {language} language only."""
                    },
                    {
                        "role": "user",
                        "content": "Generate an opening question for a memory preservation interview."
                    }
                ],
                max_tokens=100
            )

            initial_question = response.choices[0].message.content
            session_id = uuid4()
            now = datetime.utcnow()

            # Create session record...
            session_data = {
                "id": str(session_id),
                "profile_id": str(profile_id),
                "category": "general",
                "started_at": now.isoformat(),
                "emotional_state": {"initial": "neutral"},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

            logger.debug(f"Creating session with data: {session_data}")

            # Insert the session into Supabase
            result = self.supabase.table("interview_sessions").insert(
                session_data
            ).execute()

            logger.debug(f"Session creation result: {result}")

            if not result.data:
                raise Exception("Failed to create interview session record")

            return {
                "session_id": str(session_id),
                "initial_question": initial_question or "Tell me about a memorable moment from your life.",
                "started_at": now.isoformat(),
                "profile_id": str(profile_id)
            }

        except Exception as e:
            logger.error(f"Error starting interview session: {str(e)}")
            raise Exception(f"Failed to start interview session: {str(e)}")

    async def process_interview_response(
        self,
        profile_id: UUID,
        session_id: UUID,
        response_text: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process a response from the interviewee and generate the next question.
        """
        try:
            # First, analyze if the response is a memory and classify it
            classification = await KnowledgeManagement.analyze_response(
                response_text, 
                self.openai_client,
                language
            )

            logger.info("------- Analyzed response -------")
            logger.info(f"is_memory={classification.is_memory} "
                      f"rewritten_text='{classification.rewritten_text}' "
                      f"category='{classification.category}' "
                      f"location='{classification.location}' "
                      f"timestamp='{classification.timestamp}'")

            # If it's a memory, store it
            if classification.is_memory:
                await self.knowledge_manager.store_memory(
                    profile_id,
                    session_id,
                    classification
                )
                
            # Analyze sentiment
            sentiment = await self._analyze_sentiment(
                classification.rewritten_text if classification.is_memory else response_text
            )

            # Generate follow-up question based on the processed response
            next_question = await self.generate_next_question(
                profile_id, 
                session_id,
                language
            )

            return {
                "sentiment": sentiment,
                "follow_up": next_question,
                "is_memory": classification.is_memory
            }

        except Exception as e:
            print(f"Error processing interview response: {str(e)}")
            return {
                "sentiment": {"joy": 0.5, "nostalgia": 0.5},
                "follow_up": "Can you tell me more about that?",
                "is_memory": False,
                "memory_id": memory.id if memory else None
            }

    async def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze the emotional content of the response.
        """
        try:
            response = self.openai_client.chat.completions.create(  # Remove await
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the emotional content of this memory and return scores from 0 to 1 for: joy, sadness, nostalgia, and intensity."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=100
            )

            # Parse the response to extract sentiment scores
            sentiment = {
                "joy": 0.5,
                "sadness": 0.0,
                "nostalgia": 0.5,
                "intensity": 0.5
            }

            return sentiment

        except Exception as e:
            print(f"Error analyzing sentiment: {str(e)}")
            return {
                "joy": 0.5,
                "sadness": 0.0,
                "nostalgia": 0.5,
                "intensity": 0.5
            }

    async def generate_next_question(self, profile_id: UUID, session_id: UUID, language: str = "en") -> str:
        """Generate the next question based on previous responses."""
        try:
            # Get previous responses...
            previous_responses = self.supabase.table("memories").select(
                "description"
            ).eq(
                "session_id", str(session_id)
            ).order(
                "created_at", desc=True
            ).limit(3).execute()

            context = ""
            if previous_responses.data:
                context = "Previous responses: " + " ".join(
                    [r["description"] for r in previous_responses.data]
                )

            # Generate follow-up question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an empathetic interviewer helping people preserve their 
                        memories. Generate a follow-up question that encourages deeper sharing and 
                        reflection. Focus on details, emotions, and sensory experiences.
                        Respond in {language} language only."""
                    },
                    {
                        "role": "user",
                        "content": f"Given this context: {context}\nGenerate an engaging follow-up question."
                    }
                ],
                max_tokens=100
            )

            next_question = response.choices[0].message.content
            return next_question

        except Exception as e:
            logger.error(f"Error generating next question: {str(e)}")
            # Return default messages in the correct language
            default_messages = {
                "en": "What other memories would you like to share today?",
                "de": "Welche anderen Erinnerungen möchten Sie heute teilen?"
                # Add more languages as needed
            }
            return default_messages.get(language, default_messages["en"])
```

### services/profile.py
```
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, UUID4
from supabase import create_client, Client
import os
import logging
from models.profile import Profile, ProfileCreate

logger = logging.getLogger(__name__)

# Service Class
class ProfileService:
    table_name = "profiles"

    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.table_name = "profiles"

    @classmethod
    async def get_all_profiles(cls) -> List[Profile]:
        """Get all profiles"""
        try:
            service = cls()
            result = service.supabase.table(service.table_name).select("*").order(
                'updated_at', desc=True
            ).execute()

            profiles = []
            for profile_data in result.data:
                try:
                    # Convert date strings
                    if isinstance(profile_data['date_of_birth'], str):
                        profile_data['date_of_birth'] = datetime.fromisoformat(
                            profile_data['date_of_birth']
                        ).date()

                    if isinstance(profile_data['created_at'], str):
                        profile_data['created_at'] = datetime.fromisoformat(
                            profile_data['created_at']
                        )

                    if isinstance(profile_data['updated_at'], str):
                        profile_data['updated_at'] = datetime.fromisoformat(
                            profile_data['updated_at']
                        )

                    profiles.append(Profile(**profile_data))
                except Exception as e:
                    logger.error(f"Error converting profile data: {str(e)}")
                    logger.error(f"Problematic profile data: {profile_data}")
                    continue

            return profiles

        except Exception as e:
            logger.error(f"Error fetching all profiles: {str(e)}")
            raise
    
    @staticmethod
    async def create_profile(profile_data: ProfileCreate) -> Profile:
        """
        Creates a new profile in the Supabase table.
        """
        try:
            # Convert profile data to dict
            data = {
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "place_of_birth": profile_data.place_of_birth,
                "gender": profile_data.gender,
                "children": profile_data.children,
                "spoken_languages": profile_data.spoken_languages,
                "profile_image_url": profile_data.profile_image_url
            }

            # Insert data into Supabase
            response = supabase.table(ProfileService.table_name).insert(data).execute()
          
            if hasattr(response, 'error') and response.error:
                raise Exception(f"Supabase error: {response.error}")

            result_data = response.data[0] if response.data else None
            if not result_data:
                raise Exception("No data returned from Supabase")

            return Profile(**result_data)
        except Exception as e:
            raise Exception(f"Failed to create profile: {str(e)}")

    async def get_profile(self, profile_id: UUID4) -> Optional[Profile]:
        """Retrieves a profile by ID"""
        try:
            logger.debug(f"Fetching profile with ID: {profile_id}")

            # Fetch the profile from Supabase
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("id", str(profile_id))\
                .execute()

            if not result.data:
                return None

            profile_data = result.data[0]

            # Convert date strings to proper date objects
            if isinstance(profile_data['date_of_birth'], str):
                profile_data['date_of_birth'] = datetime.fromisoformat(
                    profile_data['date_of_birth']
                ).date()

            if isinstance(profile_data['created_at'], str):
                profile_data['created_at'] = datetime.fromisoformat(
                    profile_data['created_at']
                )

            if isinstance(profile_data['updated_at'], str):
                profile_data['updated_at'] = datetime.fromisoformat(
                    profile_data['updated_at']
                )

            return Profile(**profile_data)

        except Exception as e:
            logger.error(f"Error in get_profile: {str(e)}")
            logger.error(f"Profile ID: {profile_id}")
            logger.error(f"Profile data: {profile_data if 'profile_data' in locals() else 'No data fetched'}")
            raise


    @staticmethod
    async def update_profile(profile_id: UUID4, profile_data: ProfileCreate) -> Profile:
        """
        Updates an existing profile by ID.
        """
        try:
            # Update data in Supabase
            response = supabase.table(ProfileService.table_name).update(profile_data.dict()).eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            if response["data"]:
                profile = Profile(**response["data"][0])
                return profile
            raise Exception("Profile not found")
        except Exception as e:
            raise Exception(f"Failed to update profile: {str(e)}")

    @staticmethod
    async def delete_profile(profile_id: UUID4) -> bool:
        """
        Deletes a profile by ID.
        """
        try:
            # Delete the profile from Supabase
            response = supabase.table(ProfileService.table_name).delete().eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            # Return True if deletion was successful
            return response["data"] is not None
        except Exception as e:
            raise Exception(f"Failed to delete profile: {str(e)}")
```

### services/knowledgemanagement.py
```
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

logger = logging.getLogger(__name__)

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
    
    @staticmethod
    async def analyze_response(response_text: str, client, language: str = "en") -> MemoryClassification:
        """Analyze user response to classify and enhance memory content"""
        try:
            # Update the prompt to handle unknown dates and locations better
            prompt = f"""Analyze the following text and classify it as a memory or not. 
            If it is a memory, rewrite it in complete sentences using a friendly and optimistic tone, 
            in first person view. Also extract the category, location, and timestamp.
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

            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a memory analysis assistant that responds in {language}. Keep the rewritten text in the original language."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = response.choices[0].message.content
            classification = MemoryClassification.parse_raw(result)

            # Set default current date if timestamp is invalid
            if classification.timestamp in ["unbekannt", "unknown", ""]:
                classification.timestamp = datetime.now().strftime("%Y-%m-%d")

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

            # TODO: Store in Neo4j knowledge graph
            # This will be implemented later to create nodes and relationships
            # in the graph database based on the memory content

            logger.info(f"Memory stored successfully")
            return stored_memory

        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}")
            raise
```
--------------

This is the configuration of FASTAPI:
------------

### main.py
```
# /main.py
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
       "app": "Noblivion Backend",
       "version": "1.0.0"
   }
    
app.include_router(v1_router, prefix="/api")
```
------------

### Storage Layer: Supabase
In Supabase we use the object storage to store binary files per client. In Supabase we use the table storage to retain memories, profiles and all other relevant data.
The unique identifier for an client is a UUIDv4. Each client can have several interview sessions.
This is the current schema in Supabase:
---------------

### storage_layer_scripts.sql
```
-- Enable necessary extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Profiles table
create table profiles (
    id uuid primary key default uuid_generate_v4(),
    first_name text not null,
    last_name text not null,
    date_of_birth date not null,
    place_of_birth text not null,
    gender text not null,
    children text[] default '{}',
    spoken_languages text[] default '{}',
    profile_image_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Interview sessions table
create table interview_sessions (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    category text not null,
    started_at timestamptz default now(),
    completed_at timestamptz,
    summary text,
    emotional_state jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Memories table
create table memories (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    session_id uuid references interview_sessions(id) on delete cascade not null,
    category text not null,
    description text not null,
    time_period date not null,
    location jsonb,
    emotions text[] default '{}',
    people jsonb[] default '{}',
    image_urls text[] default '{}',
    audio_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    sentiment_analysis jsonb
);

-- Memory sentiments table
create table memory_sentiments (
    id uuid primary key default uuid_generate_v4(),
    memory_id uuid references memories(id) on delete cascade not null,
    sentiment_data jsonb not null,
    emotional_triggers text[] default '{}',
    intensity float default 0.0,
    requires_support boolean default false,
    created_at timestamptz default now()
);

-- Achievements table
create table achievements (
    id text primary key,
    type text not null,
    titles jsonb not null, -- Multilingual titles
    descriptions jsonb not null, -- Multilingual descriptions
    icon text not null,
    color text not null,
    required_count integer not null,
    bonus_achievement_id text references achievements(id),
    created_at timestamptz default now()
);

-- Achievement progress table
create table achievement_progress (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    achievement_id text references achievements(id) on delete cascade not null,
    current_count integer default 0,
    completed boolean default false,
    unlocked_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(profile_id, achievement_id)
);

-- PDF exports table
create table pdf_exports (
    id uuid primary key default uuid_generate_v4(),
    profile_id uuid references profiles(id) on delete cascade not null,
    file_url text not null,
    generated_at timestamptz default now(),
    category text,
    date_range tstzrange,
    created_at timestamptz default now()
);

-- Triggers for updated_at timestamps
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger profiles_updated_at
    before update on profiles
    for each row
    execute function update_updated_at();

create trigger sessions_updated_at
    before update on interview_sessions
    for each row
    execute function update_updated_at();

create trigger memories_updated_at
    before update on memories
    for each row
    execute function update_updated_at();

create trigger achievement_progress_updated_at
    before update on achievement_progress
    for each row
    execute function update_updated_at();

-- Insert default achievements
insert into achievements (id, type, titles, descriptions, icon, color, required_count) values
    ('first_memories', 'memory_milestones', 
     '{"en": "Memory Keeper", "de": "Erinnerungsbewahrer"}',
     '{"en": "Shared your first 5 memories", "de": "Ihre ersten 5 Erinnerungen geteilt"}',
     'AutoStories', '#4CAF50', 5),

    ('photo_collector', 'media_sharing',
     '{"en": "Photo Collector", "de": "Fotograf"}',
     '{"en": "Added photos to 10 memories", "de": "10 Erinnerungen mit Fotos ergänzt"}',
     'PhotoLibrary', '#2196F3', 10),

    ('childhood_expert', 'category_completion',
     '{"en": "Childhood Chronicles", "de": "Kindheitserinnerungen"}',
     '{"en": "Shared 8 childhood memories", "de": "8 Kindheitserinnerungen geteilt"}',
     'ChildCare', '#9C27B0', 8),

    ('family_historian', 'family_connection',
     '{"en": "Family Historian", "de": "Familienchronist"}',
     '{"en": "Mentioned 10 different family members", "de": "10 verschiedene Familienmitglieder erwähnt"}',
     'People', '#FF9800', 10),

    ('consistent_sharing', 'session_streaks',
     '{"en": "Regular Storyteller", "de": "Regelmäßiger Erzähler"}',
     '{"en": "Completed 5 interview sessions", "de": "5 Interviewsitzungen abgeschlossen"}',
     'Timer', '#FF5722', 5),

    ('emotional_journey', 'emotional_sharing',
     '{"en": "Heart of Gold", "de": "Herz aus Gold"}',
     '{"en": "Shared deeply emotional memories", "de": "Emotional bedeutsame Erinnerungen geteilt"}',
     'Favorite', '#E91E63', 3);

-- RLS Policies
alter table profiles enable row level security;
alter table interview_sessions enable row level security;
alter table memories enable row level security;
alter table memory_sentiments enable row level security;
alter table achievement_progress enable row level security;
alter table pdf_exports enable row level security;

-- Create indexes for better performance
create index idx_memories_profile_id on memories(profile_id);
create index idx_memories_session_id on memories(session_id);
create index idx_memories_time_period on memories(time_period);
create index idx_sessions_profile_id on interview_sessions(profile_id);
create index idx_achievement_progress_profile on achievement_progress(profile_id);
create index idx_memory_sentiments_memory on memory_sentiments(memory_id);

-- Create view for achievement statistics
create view achievement_statistics as
select 
    p.id as profile_id,
    p.first_name,
    p.last_name,
    count(distinct ap.achievement_id) as completed_achievements,
    count(distinct m.id) as total_memories,
    count(distinct m.id) filter (where m.image_urls != '{}') as memories_with_photos,
    count(distinct m.session_id) as total_sessions
from profiles p
left join achievement_progress ap on p.id = ap.profile_id and ap.completed = true
left join memories m on p.id = m.profile_id
group by p.id, p.first_name, p.last_name;

-- Storage configuration (run this after creating the bucket in Supabase dashboard)
insert into storage.buckets (id, name) values ('profile-images', 'Profile Images') on conflict do nothing;
insert into storage.buckets (id, name) values ('memory-media', 'Memory Media') on conflict do nothing;
insert into storage.buckets (id, name) values ('exports', 'PDF Exports') on conflict do nothing;
```
---------------
We will use the supabase Python client.

### AI models: OpenAI
The backend uses OpenAI API and langchain to send prompts to an AI.