from neo4j import GraphDatabase
from neo4j_graphrag.indexes import create_vector_index
import os

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

INDEX_NAME = "vector_index_noblivion"

# Connect to Neo4j database
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Creating the index
create_vector_index(
    driver,
    INDEX_NAME,
    label="Chunk",
    embedding_property="embedding",
    dimensions=1536,
    similarity_fn="euclidean",
    fail_if_exists=True,
)