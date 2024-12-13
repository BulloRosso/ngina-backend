# Test for neo 4j
import neo4j
from neo4j_graphrag.llm import OpenAILLM as LLM
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings as Embeddings
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import VectorRetriever
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

  # 1. Build KG and Store in Neo4j Database
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
  await kg_builder_txt.run_async(text="""
  **Horst Winklers Reise durch Europa**  

  Horst Winkler, ein 52-jähriger Hobbyfotograf aus München, beschloss, eine Abenteuerreise durch Europa zu unternehmen. Mit seinem alten, aber zuverlässigen VW-Bus plante er, in drei Länder zu reisen, um neue Menschen und Kulturen kennenzulernen.  

  ### **1. Halt: Frankreich**  
  Horst begann seine Reise in Frankreich und machte Halt in einem kleinen Dorf in der Provence. Dort traf er:  

  1. **Marie-Louise Chavot**, eine ältere Dame, die einen charmanten kleinen Blumenladen führte. Sie erzählte ihm Geschichten über die Provence und schenkte ihm einen Lavendelstrauß.  
  2. **Jean-Pierre Laroche**, einen Imker, der Horst beibrachte, wie man Honig aus einer Wabe gewinnt.  
  3. **Chloé Garnier**, eine junge Künstlerin, die ihre Bilder am Marktplatz verkaufte.  

  Während seines Aufenthalts in Frankreich begegnete Horst auch **Fidèle**, einem freundlichen Golden Retriever, der ihn auf einem Spaziergang durch die Weinberge begleitete.  

  ### **2. Halt: Italien**  
  Die nächste Station führte Horst nach Italien, genauer gesagt in die Toskana. Hier traf er:  

  4. **Giovanni Moretti**, einen lebensfrohen Winzer, der Horst eine private Weinverkostung anbot.  
  5. **Lucia Bellini**, die Köchin eines kleinen Trattorias, wo Horst die beste Lasagne seines Lebens aß.  
  6. **Antonio Rossi**, einen Straßenmusiker, dessen Mandolinenspiel die Piazza zum Leben erweckte.  

  In Italien stieß Horst auf **Micio**, eine getigerte Katze, die ihm in einem kleinen Olivenhain Gesellschaft leistete.  

  ### **3. Halt: Spanien**  
  Der letzte Teil seiner Reise führte ihn nach Spanien, in ein Küstendorf in Katalonien. Hier lernte er kennen:  

  7. **Isabel Torres**, eine junge Surflehrerin, die Horst zu einer Surfstunde überredete – mit mäßigem Erfolg.  
  8. **Carlos Fernández**, einen alten Fischer, der Horst beibrachte, wie man ein Netz auswirft.  
  9. **Elena Martínez**, die Besitzerin einer kleinen Buchhandlung, die Horst ein altes Reisebuch schenkte.  
  10. **Rafael Gómez**, einen talentierten Sandkünstler, der am Strand Skulpturen baute.  

  In Spanien begegnete er schließlich **Pepita**, einem neugierigen Papagei, der jeden seiner Schritte kommentierte und für einige Lacher sorgte.  

  ### **Heimkehr**  
  Nach drei Wochen voller Abenteuer kehrte Horst mit einem Herzen voller Erinnerungen nach München zurück. Er hatte nicht nur 10 einzigartige Menschen und 3 liebenswerte Haustiere kennengelernt, sondern auch seine Liebe für die kleinen, unerwarteten Begegnungen des Lebens neu entdeckt.
  """)
  
  # 2. KG Retriever
  vector_retriever = VectorRetriever(
     neo4j_driver,
     index_name="vector_index_noblivion",
     embedder=embedder
  )
  
  # 3. GraphRAG Class
  llm = LLM(model_name="gpt-4o")
  rag = GraphRAG(llm=llm, retriever=vector_retriever)
  
  # 4. Run
  response = rag.search( "Welche Personen lernte Horst Winkler auf seinen Reisen kennen?")
  print(response.answer)

print("Starting neo4j graph query:")
asyncio.run(graphrag())
