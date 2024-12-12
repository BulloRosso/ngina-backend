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
{backend_models}
----------------------
These are the endpoints:
----------------------
{backend_api_endpoints}
----------------------
When you change existing endpoints give a clear notice.

These are the exitsing backend services:
--------------
{backend_services}
--------------

This is the configuration of FASTAPI:
------------
{backend_entrypoint}
------------

### Storage Layer: Supabase
In Supabase we use the object storage to store binary files per client. In Supabase we use the table storage to retain memories, profiles and all other relevant data.
The unique identifier for an client is a UUIDv4. Each client can have several interview sessions.
This is the current schema in Supabase:
---------------
{storage_layer}
---------------
We will use the supabase Python client.

### AI models: OpenAI
The backend uses OpenAI API and langchain to send prompts to an AI.