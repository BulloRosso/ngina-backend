from neo4j import GraphDatabase
from neo4j_graphrag.indexes import create_fulltext_index
import os

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

INDEX_NAME = "fulltext_index_noblivion"

# Connect to Neo4j database
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Creating the index
create_fulltext_index(
    driver,
    INDEX_NAME,
    label="Chunk",
    node_properties=["text"],
    fail_if_exists=True,
)