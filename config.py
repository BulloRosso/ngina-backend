# config.py
from dotenv import load_dotenv
import os

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PWD")