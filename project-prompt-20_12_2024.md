# Noblivion - Your experiences are precious
Noblivion is a AI system which helps you capturing your personal or professional experiences during various on-screen interviews. The empathetic AI interviewer guides you through the depths of your memories, captures them, gives them structure and finally ouputs them as a book in PDF format.

## How to get Noblivion?
Noblivion is a gift from children to their parents and the process starts when a person enters the personal data of another person (called the client from here) as profile in the Noblivion React frontend. This profile contains personal information and will help the AI interviewer to get started and to focus on the most relevant facets of the client.

## Registration process
### 1. User creation
To create a profile you need to sign up/register with the noblivion system. 
A registered user can be found in the supabase table "users":
* a registered user has an unique "id" property of type UUID
* a registered user has a email which is used for notification mails
* a registered user has a profile property of the type JSONB
The profile property looks like this:
```
{
  "signup_secret": "03212476",
  "is_validated_by_email": true,
  "profiles": [
      { "id": "9aa460e7-9c5d-40c7-ad51-b67d0130336e", "isDefault": true }
  ]
}
```
One registered user can have more than one profiles. 

### 2. Profile creation
A registed user can create one or more profiles. Each profile is written to the profile property of the 
supabase table "users".
The profiles are stored in the supabase table "profiles".
Each profile has at least these fields/properties:
* a profile has a unique "id" property of type UUID
* a profile has a date of birth in ISO format (without time)
* a profile has a geneder property like "male"
* a profile has profile_image_url which is a full URL pointing to an avatar image on a public webserver
* a profile has a metadata property of the type JSONB

The metadata property looks like this:
```
{
  "backstory": "<about the life of the person>"
}
```
Each profile accumulates memories by having interview sessions between the empathetic interviewer AI and the user.

### 3. Interview sessions for a profile
Each interview is started to aquire memories from the user.
A interview is stored in the supabase table "interview_sessions".
Each interview has at least these fields/properties:
* a interview has a unique "id" property of type UUID
* a assigned profile (Foreign key) via the field name profile_id
* a started_at timestamp (timestamptz)
* a summary (text)
Each night an AI agent fills the summary of the interviews which are older than 6 hours by analyzing the
memories of this sessions.

### 4. Memories collected during an interview session
Each memory belongs to a session and is stored in the supabase table "memories". 
Each memory has at least these fields/properties:
* a memory has a unique "id" property of type UUID
* an assigned profile (Foreign key) via the field name profile_id
* an assigned session (Foreign key) via the field name session_id
* a category (text) which is travel | childhood | relationships | pets | hobbies | career
* a description (text) which contains the core information
* a time_period (date) which marks the start of the memory
* a location (jsonb) with the properties "city", "name", "county" and "description"
* a image_urls (text[]) which contains the full URLs of images of the memory. A memory can contain 0 or more images
* 

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

#### Local storage for state management
In the localStorage we have the following items:
* i18nextLng: The current selected locale (Example "de")
* token: the OAuth token received from the backend for the current user
* user: a JSON object of the current user. Example: {"id":"e7f8856b-165a-4bf8-b3ae-551fb58472b9","email":"ralph.goellner@e-ntegration.de","first_name":"Ralph","last_name":"Göllner","is_validated":false}
* profileId: the id of the current selected profile Example: "8f43b7d5-31d2-4f32-b956-195a83bef907"

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
    audio_url: Optional[str] = None

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
    user_id: UUID

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
from typing import List, Optional, Dict, Any

class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    gender: str
    children: List[str] = []
    spoken_languages: List[str] = []
    profile_image_url: Optional[str]
    metadata: Optional[Dict[str, Any]] = {}

class Profile(ProfileCreate):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    subscribed_at: Optional[datetime] = None
    
    @property
    def is_subscribed(self) -> bool:
        return self.subscribed_at is not None
    
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
from .auth  import router as auth_router
from .chat  import router as chat_router

router = APIRouter(prefix="/v1")
router.include_router(interviews_router)
router.include_router(memories_router)
router.include_router(achievements_router)
router.include_router(profiles_router)
router.include_router(auth_router)
router.include_router(chat_router)
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
            user_id=response.user_id,
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
from fastapi import APIRouter, HTTPException, File, Form, Query, UploadFile
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
from io import BytesIO
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
    profile: str = Form(...),
    language: str = Form("en")  # Add language parameter with default "en"
):
    try:
        profile_data = json.loads(profile)
        first_name = profile_data.get("first_name")
        last_name = profile_data.get("last_name")
        profile_data["date_of_birth"] = datetime.strptime(profile_data["date_of_birth"], "%Y-%m-%d").date()

        if not first_name or not last_name:
            raise ValueError("Both first_name and last_name are required.")

        # Sanitize filename - handle non-ASCII characters
        def sanitize_filename(s: str) -> str:
            # Replace umlauts and special characters
            replacements = {
                'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
                'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
                'é': 'e', 'è': 'e', 'ê': 'e',
                'á': 'a', 'à': 'a', 'â': 'a',
                'ó': 'o', 'ò': 'o', 'ô': 'o',
                'í': 'i', 'ì': 'i', 'î': 'i',
                'ú': 'u', 'ù': 'u', 'û': 'u'
            }

            for german, english in replacements.items():
                s = s.replace(german, english)

            # Keep only ASCII chars, numbers, and safe special chars
            return "".join(c for c in s if c.isascii() and (c.isalnum() or c in "_-"))

        safe_first_name = sanitize_filename(first_name)
        safe_last_name = sanitize_filename(last_name)
        file_extension = profile_image.filename.split(".")[-1].lower()
        file_path = f"{safe_first_name}_{safe_last_name}.{file_extension}"

        # Read file content as bytes
        file_content = await profile_image.read()

        try:
            # Remove existing file if it exists
            try:
                supabase.storage.from_("profile-images").remove([file_path])
                logger.debug(f"Removed existing file: {file_path}")
            except Exception as e:
                logger.debug(f"No existing file to remove or removal failed: {str(e)}")

            # Upload new file with raw bytes
            result = supabase.storage.from_("profile-images").upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": profile_image.content_type
                }
            )

            logger.debug(f"Upload result: {result}")

            # Get public URL
            image_url = supabase.storage.from_("profile-images").get_public_url(file_path)
            profile_data["profile_image_url"] = image_url

            logger.debug(f"Successfully uploaded image, URL: {image_url}")

            # Create profile using service with language parameter
            profile_create = ProfileCreate(**profile_data)
            return await ProfileService.create_profile(profile_create, language=language)

        except Exception as e:
            logger.error(f"Storage error: {str(e)}")
            logger.error(f"Error details: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing profile image: {str(e)}"
            )

    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        error_info = f"Error in {tb.filename}, line {tb.lineno}: {str(e)}"
        logger.error(f"Validation error: {error_info}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
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

@router.delete("/{profile_id}")
async def delete_profile(profile_id: UUID):
    """Delete a profile and all associated data"""
    try:
        logger.debug(f"Deleting profile with ID: {profile_id}")
        service = ProfileService()

        # Delete profile and all associated data
        success = await service.delete_profile(profile_id)

        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"message": "Profile and all associated data deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting profile: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
```

### api/v1/auth.py
```
# api/v1/auth.py
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
from config.jwt import create_access_token
from supabase import create_client
import os
import bcrypt
from services.email import EmailService
import random
import string
from config.jwt import decode_token
import logging
from typing import Dict, Optional
import json

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

class ProfileUpdate(BaseModel):
    profile: Dict

async def get_current_user(authorization: str = Header(None)) -> str:
    """Get current user from authorization header"""
    if not authorization:
        logger.error("No authorization header provided")
        raise HTTPException(
            status_code=401,
            detail="No authorization header"
        )

    try:
        logger.debug(f"Processing authorization header: {authorization[:20]}...")
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            logger.error(f"Invalid authentication scheme: {scheme}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme"
            )

        logger.debug("Attempting to decode token...")
        payload = decode_token(token)
        if not payload:
            logger.error("Token decode returned None")
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        user_id = payload.get("sub")
        if not user_id:
            logger.error("No user ID in token payload")
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )

        logger.debug(f"Successfully validated token for user: {user_id}")
        return user_id
    except ValueError as e:
        logger.error(f"Invalid authorization header format: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )
    except Exception as e:
        logger.error(f"Error validating token: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token"
        )

def generate_verification_code():
    return ''.join(random.choices(string.digits, k=8))
    
class LoginRequest(BaseModel):
    email: str
    password: str
    
class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

class VerificationRequest(BaseModel):
    code: str
    user_id: str
    
# api/v1/auth.py
@router.post("/signup")
async def signup(request: SignupRequest):
    try:
        # Check if user exists
        result = supabase.table("users").select("*").eq("email", request.email).execute()
        if result.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Generate verification code
        verification_code = generate_verification_code()

        # Create user with verification code in profile
        user_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "password": bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            "profile": {
                "signup_secret": verification_code,
                "is_validated_by_email": False
            }
        }

        result = supabase.table("users").insert(user_data).execute()
        user = result.data[0]

        # Send verification email (synchronously)
        email_service = EmailService()
        email_service.send_verification_email(request.email, verification_code)  # Removed await

        # Create access token
        access_token = create_access_token(data={"sub": user["id"], "email": user["email"]})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "is_validated": False
            }
        }
    except Exception as e:
        print(f"Signup error: {str(e)}")  # Add debug logging
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/validation-status/{user_id}")
async def check_validation_status(user_id: str):
    """Check if a user's email is validated"""
    try:
        # Query user from Supabase
        result = supabase.table("users").select("profile").eq("id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]
        profile = user.get("profile", {})

        # Check validation status from profile JSONB
        is_validated = profile.get("is_validated_by_email", False)

        return {
            "is_validated": is_validated,
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"Error checking validation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check validation status: {str(e)}"
        )
        
@router.post("/verify-email")
async def verify_email(verification_data: VerificationRequest):
    try:
        # Get user
        result = supabase.table("users").select("*").eq(
            "id", verification_data.user_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]
        profile = user.get("profile", {})

        # Check verification code
        if profile.get("signup_secret") != verification_data.code:
            return {"verified": False}

        # Update user profile
        profile["is_validated_by_email"] = True
        supabase.table("users").update(
            {"profile": profile}
        ).eq("id", verification_data.user_id).execute()

        return {"verified": True}
    except Exception as e:
        print(f"Verification error: {str(e)}")  # Add debug logging
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resend-verification")
async def resend_verification(user_id: str):
    try:
        # Get user
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]

        # Generate new verification code
        verification_code = generate_verification_code()

        # Update user profile
        profile = user.get("profile", {})
        profile["signup_secret"] = verification_code
        supabase.table("users").update({"profile": profile}).eq("id", user_id).execute()

        # Send new verification email
        email_service = EmailService()
        await email_service.send_verification_email(user["email"], verification_code)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(login_data: LoginRequest):  # Use Pydantic model for validation
    try:
        print(f"Login attempt for email: {login_data.email}")  # Debug logging

        # Get user from Supabase
        result = supabase.table("users").select("*").eq("email", login_data.email).execute()

        if not result.data:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email or password"
            )

        user = result.data[0]

        # Verify password
        is_valid = bcrypt.checkpw(
            login_data.password.encode('utf-8'),
            user["password"].encode('utf-8')
        )

        if not is_valid:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token(
            data={"sub": user["id"], "email": user["email"]}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")  # Debug logging
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get user profile settings"""
    try:
        logger.debug(f"Getting profile for user ID: {user_id}")

        # Verify user is accessing their own profile
        if current_user != user_id:
            logger.warning(f"User {current_user} attempted to access profile of {user_id}")
            raise HTTPException(
                status_code=403,
                detail="Cannot access another user's profile"
            )

        result = supabase.table("users").select("profile").eq("id", user_id).execute()

        if not result.data:
            logger.warning(f"No profile found for user {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        profile_data = result.data[0].get("profile", {})

        # Ensure default fields exist
        profile_data.setdefault("signup_secret", "")
        profile_data.setdefault("is_validated_by_email", False)
        profile_data.setdefault("narrator_perspective", "ego")
        profile_data.setdefault("narrator_verbosity", "normal")
        profile_data.setdefault("narrator_style", "neutral")

        logger.debug(f"Successfully retrieved profile for user {user_id}")
        return {"profile": profile_data}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile")
async def update_user_profile(
    profile_update: ProfileUpdate,
    current_user: str = Depends(get_current_user)
):
    """Update user profile settings"""
    try:
        logger.info(f"Updating profile for user ID: {current_user}")

        # Get current profile to merge with new settings
        current_result = supabase.table("users").select("profile").eq("id", current_user).execute()

        if not current_result.data:
            logger.warning(f"No profile found for user {current_user}")
            raise HTTPException(status_code=404, detail="User not found")

        current_profile = current_result.data[0].get("profile", {})

        # Ensure required fields are preserved
        updated_profile = {
            "signup_secret": current_profile.get("signup_secret", ""),
            "is_validated_by_email": current_profile.get("is_validated_by_email", False),
            **profile_update.profile
        }

        # Update profile in database
        result = supabase.table("users").update(
            {"profile": updated_profile}
        ).eq("id", current_user).execute()

        if not result.data:
            logger.error(f"Failed to update profile for user {current_user}")
            raise HTTPException(status_code=404, detail="Failed to update profile")

        logger.info(f"Successfully updated profile for user {current_user}")
        return {"message": "Profile updated successfully", "profile": updated_profile}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

### api/v1/chat.py
```
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
                    "time_period": str(memory.time_period),
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
            # First, fetch the profile to get the backstory
            profile_result = self.supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()

            if not profile_result.data:
                raise Exception("Profile not found")

            profile = profile_result.data[0]
            backstory = profile.get("metadata", {}).get("backstory", "")
            name = f"{profile['first_name']} {profile['last_name']}"

            # Create system prompt with backstory context and language
            system_prompt = f"""You are an empathetic interviewer helping {name} preserve their memories.

            Context about {name}:
            {backstory if backstory else "No previous context available."}

            Generate a warm, inviting opening question in {language} that:
            1. Makes the person feel comfortable sharing memories
            2. References their background if available
            3. Is open-ended but specific enough to trigger memories
            4. Uses appropriate cultural references based on their background

            The entire response should be in {language} language only."""

            # Generate personalized opening question using OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Generate an opening question for {name}'s memory preservation interview."
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )

            initial_question = response.choices[0].message.content
            session_id = uuid4()
            now = datetime.utcnow()

            # Create session record
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
                "initial_question": initial_question,
                "started_at": now.isoformat(),
                "profile_id": str(profile_id)
            }

        except Exception as e:
            logger.error(f"Error starting interview session: {str(e)}")
            raise Exception(f"Failed to start interview session: {str(e)}")
            
    async def process_interview_response(
        self,
        user_id: UUID,
        profile_id: UUID,
        session_id: UUID,
        response_text: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process a response from the interviewee and generate the next question.
        """
        try:
            # First, get profile settings
            profile_result = self.supabase.table("users").select("profile").eq(
                "id", str(user_id)
            ).execute()

            if not profile_result.data:
                raise Exception(f"Profile not found {user_id}")

            profile_settings = profile_result.data[0].get("profile", {})

            # Get narrative settings with defaults
            narrator_perspective = profile_settings.get("narrator_perspective", "ego")
            narrator_style = profile_settings.get("narrator_style", "neutral")
            narrator_verbosity = profile_settings.get("narrator_verbosity", "normal")

            logger.debug(f"Using profile settings - perspective: {narrator_perspective}, style: {narrator_style}, verbosity: {narrator_verbosity}")

            # Analyze if the response is a memory and classify it with profile settings
            classification = await KnowledgeManagement.analyze_response(
                response_text=response_text, 
                client=self.openai_client,
                language=language,
                narrator_perspective=narrator_perspective,
                narrator_style=narrator_style,
                narrator_verbosity=narrator_verbosity
            )

            logger.info("------- Analyzed response -------")
            logger.info(f"is_memory={classification.is_memory} "
                      f"category='{classification.category}' "
                      f"location='{classification.location}' "
                      f"timestamp='{classification.timestamp}'")

            # If it's a memory, store it
            if classification.is_memory:
                logger.info(f"rewrittenText='{classification.rewritten_text}'")
                logger.info(f"narrator_perspective='{narrator_perspective}'")
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
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4
from supabase import create_client, Client
import os
import logging
import json
from models.profile import Profile, ProfileCreate
from models.memory import MemoryCreate, Category, Memory, Location
from services.memory import MemoryService
import openai
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Service Class
class ProfileService:
    table_name = "profiles"

    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.openai_client = openai.Client(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    async def parse_backstory(self, profile_id: UUID, backstory: str, profile_data: Dict[str, Any], language: str = "de") -> None:
        """Parse memories from backstory and create initial memories in the specified language"""
        try:
            logger.info(f"Parsing backstory for profile {profile_id} in language {language}")

            # Create single session for all initial memories
            session_data = {
                "id": str(uuid4()),
                "profile_id": str(profile_id),
                "category": "initial",
                "started_at": datetime.utcnow().isoformat(),
                "emotional_state": {"initial": "neutral"},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Create session
            try:
                session_result = self.supabase.table("interview_sessions").insert(session_data).execute()
                if not session_result.data:
                    raise Exception("Failed to create interview session")
                session_id = session_result.data[0]['id']
                logger.info(f"Created interview session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to create interview session: {str(e)}")
                raise

            # Use the same session_id for all memories

            # Create birth memory
            try:
                city = profile_data['place_of_birth'].split(',')[0].strip()
                country = profile_data['place_of_birth'].split(',')[-1].strip()

                birth_description = {
                    "de": f"{profile_data['first_name']} {profile_data['last_name']} wurde in {profile_data['place_of_birth']} geboren",
                    "en": f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}"
                }.get(language, f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}")

                birth_memory = MemoryCreate(
                    category=Category.CHILDHOOD,
                    description=birth_description,
                    time_period=datetime.strptime(profile_data['date_of_birth'], "%Y-%m-%d"),
                    location=Location(
                        name=profile_data['place_of_birth'],
                        city=city,
                        country=country,
                        description="Geburtsort" if language == "de" else "Place of birth"
                    )
                )

                await MemoryService.create_memory(birth_memory, profile_id, session_id)
                logger.info("Birth memory created successfully")

            except Exception as e:
                logger.error(f"Error creating birth memory: {str(e)}")

            # Get narrator settings from user profile
            user_result = self.supabase.table("users").select("profile").eq("id", str(profile_id)).execute()
            user_profile = user_result.data[0].get("profile", {}) if user_result.data else {}

            # Get narrative settings with defaults
            narrator_perspective = user_profile.get("narrator_perspective", "ego")
            narrator_style = user_profile.get("narrator_style", "neutral")
            narrator_verbosity = user_profile.get("narrator_verbosity", "normal")

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

            logger.debug(f"Using narrative settings - perspective: {perspective_text}, style: {style_text}, verbosity: {verbosity_text}, temperature: {temperature}")
            
            # Parse and create additional memories using the SAME session_id
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Extract distinct memories from the backstory and format them as a JSON object.
                            The date is a single string in the format "YYYY-MM-DD". If it is a timespan always use the start date.
                            Write all text content in {language} language.

                            Format each memory {perspective_text}, {style_text}. 
                            Compared to the source text, your description should be {verbosity_text}.

                            For each memory in the "memories" array, provide:
                            {{
                                "description": "Full description of the memory in {language}",
                                "category": "One of: childhood/career/relationships/travel/hobbies/pets",
                                "date": "YYYY-MM-DD (approximate if not specified)",
                                "location": {{
                                    "name": "Location name",
                                    "city": "City if mentioned",
                                    "country": "Country if mentioned",
                                    "description": "Brief description of the location in {language}"
                                }}
                            }}"""
                        },
                        {
                            "role": "user",
                            "content": f"Please analyze this text and return the memories as JSON: {backstory}"
                        }
                    ],
                    response_format={ "type": "json_object" },
                    temperature=temperature
                )

                try:
                    parsed_memories = json.loads(response.choices[0].message.content)
                    logger.info(f"Parsed memories: {parsed_memories}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Raw response: {response.choices[0].message.content}")
                    raise Exception("Failed to parse OpenAI response")

                # Create all memories using the same session_id
                for memory_data in parsed_memories.get('memories', []):
                    try:
                        category_str = memory_data.get('category', 'childhood').upper()
                        category = getattr(Category, category_str, Category.CHILDHOOD)

                        logger.info("------------------- parsed memory -----------")
                        logger.info(category)
                        logger.info(memory_data.get('description'))
                        logger.info(memory_data.get('date'))

                        memory = MemoryCreate(
                            category=category,
                            description=memory_data['description'],
                            time_period=memory_data.get('date'),
                            location=Location(**memory_data['location']) if memory_data.get('location') else None
                        )

                        # Use the same session_id for all memories
                        await MemoryService.create_memory(memory, profile_id, session_id)
                        logger.debug(f"Created memory: {memory.description}")

                    except Exception as e:
                        logger.error(f"Error creating individual memory: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"Error parsing memories from backstory: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error in parse_backstory: {str(e)}")
            raise Exception(f"Failed to parse backstory: {str(e)}")
            
    @classmethod
    async def get_all_profiles(cls) -> List[Profile]:
        """Get all profiles"""
        try:
            service = cls()
            
            # Direct SQL query to get profiles with their session counts
            query = """
                SELECT p.*,
                       (SELECT COUNT(*) 
                        FROM interview_sessions 
                        WHERE profile_id = p.id) as session_count
                FROM profiles p
                ORDER BY p.updated_at DESC
            """

            result = service.supabase.table('profiles').select("*").execute()
            
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
                    
                    if isinstance(profile_data['subscribed_at'], str):
                        profile_data['subscribed_at'] = datetime.fromisoformat(profile_data['subscribed_at'])
                    else:
                        profile_data['subscribed_at'] = None
                        
                    # Initialize metadata if it doesn't exist
                    if not profile_data.get('metadata'):
                        profile_data['metadata'] = {}

                    # Add session count to metadata
                    session_count_result = service.supabase.table('interview_sessions')\
                        .select('id', count='exact')\
                        .eq('profile_id', profile_data['id'])\
                        .execute()

                    profile_data['metadata']['session_count'] = session_count_result.count
                    
                    profiles.append(Profile(**profile_data))
                except Exception as e:
                    logger.error(f"Error converting profile data: {str(e)}")
                    logger.error(f"Problematic profile data: {profile_data}")
                    continue

            return profiles

        except Exception as e:
            logger.error(f"Error fetching all profiles: {str(e)}")
            raise

    @classmethod
    async def create_profile(cls, profile_data: ProfileCreate, language: str = "en") -> Profile:
        """Creates a new profile and initializes memories from backstory"""
        try:
            service = cls()  # Create instance

            # Extract backstory from metadata if present
            backstory = None
            metadata = profile_data.metadata if hasattr(profile_data, 'metadata') else {}
            if isinstance(metadata, dict):
                backstory = metadata.get('backstory')

            # Prepare profile data for database
            data = {
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "place_of_birth": profile_data.place_of_birth,
                "gender": profile_data.gender,
                "children": profile_data.children,
                "spoken_languages": profile_data.spoken_languages,
                "profile_image_url": profile_data.profile_image_url,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Insert profile into database
            result = service.supabase.table(service.table_name).insert(data).execute()

            if not result.data:
                raise Exception("No data returned from profile creation")

            profile_id = result.data[0]['id']
            created_profile = Profile(**result.data[0])

            # Parse backstory and create initial memories if backstory exists
            if backstory:
                await service.parse_backstory(
                    profile_id=profile_id,
                    backstory=backstory,
                    profile_data=data,
                    language=language  # Pass the language parameter
                )

            return created_profile

        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
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
        Deletes a profile and all associated data by ID.
        """
        try:
            service = ProfileService()

            # First get the profile to check if it exists and get image URL
            result = service.supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()

            if not result.data:
                return False

            profile = result.data[0]

            # Delete profile image from storage if it exists
            if profile.get('profile_image_url'):
                try:
                    # Extract filename from URL
                    filename = profile['profile_image_url'].split('/')[-1]
                    service.supabase.storage.from_("profile-images").remove([filename])
                    logger.debug(f"Deleted profile image: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete profile image: {str(e)}")

            # Delete all related data
            # Note: Due to cascade delete in Supabase, we only need to delete the profile
            result = service.supabase.table("profiles").delete().eq("id", str(profile_id)).execute()

            if result.data:
                logger.info(f"Successfully deleted profile {profile_id} and all associated data")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete profile {profile_id}: {str(e)}")
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
import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import VectorRetriever
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
        language: str = "en",
        narrator_perspective: str = "ego",
        narrator_style: str = "neutral",
        narrator_verbosity: str = "normal"
    ) -> MemoryClassification:
        """Analyze user response to classify and enhance memory content with profile settings"""
        try:
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
```

### services/email.py
```
# services/email.py
import os
from mailersend import emails
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.api_key = os.getenv('MAILERSEND_API_KEY')
        self.sender_domain = os.getenv('MAILERSEND_SENDER_EMAIL')
        self.mailer = emails.NewEmail(self.api_key)

    def send_verification_email(self, to_email: str, verification_code: str):
        try:
            # Read template
            template_path = Path("templates/account-verification-en.html")
            with open(template_path, "r") as f:
                html_content = f.read()

            # Replace placeholder
            html_content = html_content.replace("{verification_code}", verification_code)

            # Prepare empty mail body
            mail_body = {}

            # Set sender
            mail_from = {
                "name": "Noblivion",
                "email": self.sender_domain
            }
            self.mailer.set_mail_from(mail_from, mail_body)

            # Set recipient
            recipients = [
                {
                    "name": to_email,
                    "email": to_email
                }
            ]
            self.mailer.set_mail_to(recipients, mail_body)

            # Set subject
            self.mailer.set_subject("Verify your Noblivion account", mail_body)

            # Set content
            self.mailer.set_html_content(html_content, mail_body)
            self.mailer.set_plaintext_content(
                f"Your verification code is: {verification_code}", 
                mail_body
            )

            # Send email synchronously
            return self.mailer.send(mail_body)

        except Exception as e:
            print(f"Failed to send verification email: {str(e)}")
            raise
```

### services/profile.py
```
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4
from supabase import create_client, Client
import os
import logging
import json
from models.profile import Profile, ProfileCreate
from models.memory import MemoryCreate, Category, Memory, Location
from services.memory import MemoryService
import openai
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Service Class
class ProfileService:
    table_name = "profiles"

    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.openai_client = openai.Client(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    async def parse_backstory(self, profile_id: UUID, backstory: str, profile_data: Dict[str, Any], language: str = "de") -> None:
        """Parse memories from backstory and create initial memories in the specified language"""
        try:
            logger.info(f"Parsing backstory for profile {profile_id} in language {language}")

            # Create single session for all initial memories
            session_data = {
                "id": str(uuid4()),
                "profile_id": str(profile_id),
                "category": "initial",
                "started_at": datetime.utcnow().isoformat(),
                "emotional_state": {"initial": "neutral"},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Create session
            try:
                session_result = self.supabase.table("interview_sessions").insert(session_data).execute()
                if not session_result.data:
                    raise Exception("Failed to create interview session")
                session_id = session_result.data[0]['id']
                logger.info(f"Created interview session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to create interview session: {str(e)}")
                raise

            # Use the same session_id for all memories

            # Create birth memory
            try:
                city = profile_data['place_of_birth'].split(',')[0].strip()
                country = profile_data['place_of_birth'].split(',')[-1].strip()

                birth_description = {
                    "de": f"{profile_data['first_name']} {profile_data['last_name']} wurde in {profile_data['place_of_birth']} geboren",
                    "en": f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}"
                }.get(language, f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}")

                birth_memory = MemoryCreate(
                    category=Category.CHILDHOOD,
                    description=birth_description,
                    time_period=datetime.strptime(profile_data['date_of_birth'], "%Y-%m-%d"),
                    location=Location(
                        name=profile_data['place_of_birth'],
                        city=city,
                        country=country,
                        description="Geburtsort" if language == "de" else "Place of birth"
                    )
                )

                await MemoryService.create_memory(birth_memory, profile_id, session_id)
                logger.info("Birth memory created successfully")

            except Exception as e:
                logger.error(f"Error creating birth memory: {str(e)}")

            # Get narrator settings from user profile
            user_result = self.supabase.table("users").select("profile").eq("id", str(profile_id)).execute()
            user_profile = user_result.data[0].get("profile", {}) if user_result.data else {}

            # Get narrative settings with defaults
            narrator_perspective = user_profile.get("narrator_perspective", "ego")
            narrator_style = user_profile.get("narrator_style", "neutral")
            narrator_verbosity = user_profile.get("narrator_verbosity", "normal")

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

            logger.debug(f"Using narrative settings - perspective: {perspective_text}, style: {style_text}, verbosity: {verbosity_text}, temperature: {temperature}")
            
            # Parse and create additional memories using the SAME session_id
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Extract distinct memories from the backstory and format them as a JSON object.
                            The date is a single string in the format "YYYY-MM-DD". If it is a timespan always use the start date.
                            Write all text content in {language} language.

                            Format each memory {perspective_text}, {style_text}. 
                            Compared to the source text, your description should be {verbosity_text}.

                            For each memory in the "memories" array, provide:
                            {{
                                "description": "Full description of the memory in {language}",
                                "category": "One of: childhood/career/relationships/travel/hobbies/pets",
                                "date": "YYYY-MM-DD (approximate if not specified)",
                                "location": {{
                                    "name": "Location name",
                                    "city": "City if mentioned",
                                    "country": "Country if mentioned",
                                    "description": "Brief description of the location in {language}"
                                }}
                            }}"""
                        },
                        {
                            "role": "user",
                            "content": f"Please analyze this text and return the memories as JSON: {backstory}"
                        }
                    ],
                    response_format={ "type": "json_object" },
                    temperature=temperature
                )

                try:
                    parsed_memories = json.loads(response.choices[0].message.content)
                    logger.info(f"Parsed memories: {parsed_memories}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Raw response: {response.choices[0].message.content}")
                    raise Exception("Failed to parse OpenAI response")

                # Create all memories using the same session_id
                for memory_data in parsed_memories.get('memories', []):
                    try:
                        category_str = memory_data.get('category', 'childhood').upper()
                        category = getattr(Category, category_str, Category.CHILDHOOD)

                        logger.info("------------------- parsed memory -----------")
                        logger.info(category)
                        logger.info(memory_data.get('description'))
                        logger.info(memory_data.get('date'))

                        memory = MemoryCreate(
                            category=category,
                            description=memory_data['description'],
                            time_period=memory_data.get('date'),
                            location=Location(**memory_data['location']) if memory_data.get('location') else None
                        )

                        # Use the same session_id for all memories
                        await MemoryService.create_memory(memory, profile_id, session_id)
                        logger.debug(f"Created memory: {memory.description}")

                    except Exception as e:
                        logger.error(f"Error creating individual memory: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"Error parsing memories from backstory: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error in parse_backstory: {str(e)}")
            raise Exception(f"Failed to parse backstory: {str(e)}")
            
    @classmethod
    async def get_all_profiles(cls) -> List[Profile]:
        """Get all profiles"""
        try:
            service = cls()
            
            # Direct SQL query to get profiles with their session counts
            query = """
                SELECT p.*,
                       (SELECT COUNT(*) 
                        FROM interview_sessions 
                        WHERE profile_id = p.id) as session_count
                FROM profiles p
                ORDER BY p.updated_at DESC
            """

            result = service.supabase.table('profiles').select("*").execute()
            
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
                    
                    if isinstance(profile_data['subscribed_at'], str):
                        profile_data['subscribed_at'] = datetime.fromisoformat(profile_data['subscribed_at'])
                    else:
                        profile_data['subscribed_at'] = None
                        
                    # Initialize metadata if it doesn't exist
                    if not profile_data.get('metadata'):
                        profile_data['metadata'] = {}

                    # Add session count to metadata
                    session_count_result = service.supabase.table('interview_sessions')\
                        .select('id', count='exact')\
                        .eq('profile_id', profile_data['id'])\
                        .execute()

                    profile_data['metadata']['session_count'] = session_count_result.count
                    
                    profiles.append(Profile(**profile_data))
                except Exception as e:
                    logger.error(f"Error converting profile data: {str(e)}")
                    logger.error(f"Problematic profile data: {profile_data}")
                    continue

            return profiles

        except Exception as e:
            logger.error(f"Error fetching all profiles: {str(e)}")
            raise

    @classmethod
    async def create_profile(cls, profile_data: ProfileCreate, language: str = "en") -> Profile:
        """Creates a new profile and initializes memories from backstory"""
        try:
            service = cls()  # Create instance

            # Extract backstory from metadata if present
            backstory = None
            metadata = profile_data.metadata if hasattr(profile_data, 'metadata') else {}
            if isinstance(metadata, dict):
                backstory = metadata.get('backstory')

            # Prepare profile data for database
            data = {
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "place_of_birth": profile_data.place_of_birth,
                "gender": profile_data.gender,
                "children": profile_data.children,
                "spoken_languages": profile_data.spoken_languages,
                "profile_image_url": profile_data.profile_image_url,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Insert profile into database
            result = service.supabase.table(service.table_name).insert(data).execute()

            if not result.data:
                raise Exception("No data returned from profile creation")

            profile_id = result.data[0]['id']
            created_profile = Profile(**result.data[0])

            # Parse backstory and create initial memories if backstory exists
            if backstory:
                await service.parse_backstory(
                    profile_id=profile_id,
                    backstory=backstory,
                    profile_data=data,
                    language=language  # Pass the language parameter
                )

            return created_profile

        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
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
        Deletes a profile and all associated data by ID.
        """
        try:
            service = ProfileService()

            # First get the profile to check if it exists and get image URL
            result = service.supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()

            if not result.data:
                return False

            profile = result.data[0]

            # Delete profile image from storage if it exists
            if profile.get('profile_image_url'):
                try:
                    # Extract filename from URL
                    filename = profile['profile_image_url'].split('/')[-1]
                    service.supabase.storage.from_("profile-images").remove([filename])
                    logger.debug(f"Deleted profile image: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete profile image: {str(e)}")

            # Delete all related data
            # Note: Due to cascade delete in Supabase, we only need to delete the profile
            result = service.supabase.table("profiles").delete().eq("id", str(profile_id)).execute()

            if result.data:
                logger.info(f"Successfully deleted profile {profile_id} and all associated data")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete profile {profile_id}: {str(e)}")
            raise Exception(f"Failed to delete profile: {str(e)}")
```

### dependencies/auth.py
```
# dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from config.jwt import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
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

CREATE TABLE public.users (
    instance_id uuid, 
    id uuid NOT NULL DEFAULT uuid_generate_v4(), 
    id uuid NOT NULL, 
    first_name text NOT NULL, 
    aud character varying(255), 
    last_name text NOT NULL, 
    email text NOT NULL, role character varying(255), 
    email character varying(255), 
    password text NOT NULL, 
    encrypted_password character varying(255), 
    created_at timestamp with time zone DEFAULT now(), 
    updated_at timestamp with time zone DEFAULT now(), 
    email_confirmed_at timestamp with time zone, 
    invited_at timestamp with time zone, 
    profile jsonb DEFAULT '{"is_validated_by_email": false}'::jsonb, 
    confirmation_token character varying(255), 
    confirmation_sent_at timestamp with time zone, 
    recovery_token character varying(255), 
    recovery_sent_at timestamp with time zone, 
    email_change_token_new character varying(255), 
    email_change character varying(255), 
    email_change_sent_at timestamp with time zone, 
    last_sign_in_at timestamp with time zone, 
    raw_app_meta_data jsonb, 
    raw_user_meta_data jsonb, is_super_admin boolean, created_at timestamp with time zone, updated_at timestamp with time zone, phone text DEFAULT NULL::character varying, phone_confirmed_at timestamp with time zone, phone_change text DEFAULT ''::character varying, phone_change_token character varying(255) DEFAULT ''::character varying, phone_change_sent_at timestamp with time zone, confirmed_at timestamp with time zone, email_change_token_current character varying(255) DEFAULT ''::character varying, email_change_confirm_status smallint DEFAULT 0, banned_until timestamp with time zone, reauthentication_token character varying(255) DEFAULT ''::character varying, reauthentication_sent_at timestamp with time zone, is_sso_user boolean NOT NULL DEFAULT false, deleted_at timestamp with time zone, is_anonymous boolean NOT NULL DEFAULT false);
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