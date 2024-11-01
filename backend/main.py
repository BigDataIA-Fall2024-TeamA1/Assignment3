import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import snowflake.connector
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager
from typing import List

# Import llama_index components
from llama_index.core import Settings
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.nvidia import NVIDIAEmbedding
from llama_index.llms.nvidia import NVIDIA

from pinecone import Pinecone
from llama_index.core.schema import Document as LlamaDocument

# Load environment variables
load_dotenv()

# Configure logging with timestamps and levels
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = FastAPI()

# Global variable to hold the index
llama_index = None

# Initialize Snowflake connection
def init_snowflake():
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA'),
        )
        logging.info("Connected to Snowflake successfully.")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to Snowflake: {e}")
        raise

# Initialize llama_index Settings
def initialize_llama_index_settings():
    Settings.embed_model = NVIDIAEmbedding(
        model="nvidia/nv-embedqa-e5-v5", 
        truncate="END",
        api_key=os.getenv("NVIDIA_API_KEY")
    )
    Settings.llm = NVIDIA(
        model="meta/llama-3.2-3b-instruct",
        api_key=os.getenv("NVIDIA_API_KEY")
    )
    Settings.text_splitter = SentenceSplitter(chunk_size=600)
    logging.info("llama_index settings initialized successfully.")

# Initialize Pinecone connection
def initialize_pinecone_connection():
    try:
        Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment=os.getenv("PINECONE_ENV"))
        logging.info("Connected to Pinecone successfully.")
    except Exception as e:
        logging.error(f"Failed to connect to Pinecone: {e}")
        raise

# Create and initialize the index using llama_index with Pinecone
def create_llama_index(documents):
    try:
        vector_store = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            dimension=768
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        logging.info("VectorStoreIndex created successfully with Pinecone.")
        return index
    except Exception as e:
        logging.error(f"Failed to create VectorStoreIndex with Pinecone: {e}")
        raise

# Load documents from Snowflake
def load_documents_from_snowflake():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT TITLE, NOTE_TEXT FROM RESEARCH_NOTES;")
        rows = cursor.fetchall()
        documents = [
            LlamaDocument(doc_id=row[0], text=row[1], metadata={"title": row[0]})
            for row in rows
        ]
        cursor.close()
        conn.close()
        logging.info(f"Loaded {len(documents)} documents from Snowflake.")
        return documents
    except Exception as e:
        logging.error(f"Error loading documents from Snowflake: {e}")
        raise

# Lifespan Event Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    global llama_index
    try:
        initialize_pinecone_connection()
        initialize_llama_index_settings()
        documents = load_documents_from_snowflake()
        llama_index = create_llama_index(documents)
        yield
    finally:
        if llama_index:
            del llama_index
        logging.info("Application shutdown complete.")

# Attach the lifespan to the FastAPI app
app = FastAPI(lifespan=lifespan)

# Data Models
class ModifiedAnswerRequest(BaseModel):
    title: str
    modified_answer: str

class ResearchNoteResponse(BaseModel):
    title: str
    notes: List[str]

# Save Modified Answer as Research Note
@app.post("/save_modified_answer")
async def save_modified_answer(request: ModifiedAnswerRequest):
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        insert_query = "INSERT INTO RESEARCH_NOTES (TITLE, NOTE_TEXT) VALUES (%s, %s);"
        cursor.execute(insert_query, (request.title, request.modified_answer))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Modified answer saved as research note for document '{request.title}'.")

        # Retrieve all saved research notes for this document
        research_notes = get_research_notes(request.title)
        return {"status": "Modified answer saved successfully", "research_notes": research_notes}
    except Exception as e:
        logging.error(f"Error saving modified answer: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while saving the modified answer.")

# Fetch Research Notes for a Document
@app.get("/view_research_notes/{title}", response_model=ResearchNoteResponse)
async def view_research_notes(title: str):
    try:
        research_notes = get_research_notes(title)
        return {"title": title, "notes": research_notes}
    except Exception as e:
        logging.error(f"Error retrieving research notes: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving research notes.")

# Helper function to fetch research notes from Snowflake
def get_research_notes(title: str) -> List[str]:
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        query = "SELECT NOTE_TEXT FROM RESEARCH_NOTES WHERE TITLE = %s;"
        cursor.execute(query, (title,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        logging.info(f"Fetched {len(rows)} research notes for title: {title}")
        return [row[0] for row in rows]
    except Exception as e:
        logging.error(f"Error fetching research notes: {e}")
        raise

# Search within Research Notes
@app.get("/search_research_notes/{title}")
async def search_research_notes(title: str, query: str):
    try:
        research_notes = get_research_notes(title)
        matching_notes = [
            note for note in research_notes
            if query.lower().strip() in note.lower().strip()
        ]
        return {"title": title, "matching_notes": matching_notes}
    except Exception as e:
        logging.error(f"Error searching research notes: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while searching research notes.")

# Search Full Text of the Document
@app.get("/search_full_text/{title}")
async def search_full_text(title: str, query: str):
    try:
        if llama_index is None:
            logging.error("llama_index is not initialized.")
            raise HTTPException(status_code=500, detail="Service not initialized.")

        query_engine = llama_index.as_query_engine(similarity_top_k=5, streaming=False)
        response = query_engine.query(query)
        return {"title": title, "results": response.response if hasattr(response, 'response') else str(response)}
    except Exception as e:
        logging.error(f"Error in full-text search: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during full-text search.")

# Get List of Documents
@app.get("/documents")
async def get_documents():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT TITLE, PDF_URL FROM PUBLICATIONS_METADATA;")
        rows = cursor.fetchall()
        documents = [{"title": row[0], "pdf_url": row[1]} for row in rows]
        cursor.close()
        conn.close()
        logging.info(f"Retrieved {len(documents)} documents.")
        return documents
    except Exception as e:
        logging.error(f"Error retrieving documents: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving documents.")

# Generate Summary for a Document
@app.get("/documents/{title}/summary")
async def generate_summary(title: str):
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT SUMMARY, IMAGE_URL, PDF_URL FROM PUBLICATIONS_METADATA WHERE TITLE = %s;", (title,))
        row = cursor.fetchone()
        
        if row:
            summary = row[0] if row[0] else "No summary available for this document."
            image_url = row[1]
            pdf_url = row[2]
        else:
            summary = "No summary available for this document."
            image_url = None
            pdf_url = None
        
        cursor.close()
        conn.close()
        
        return {"summary": summary, "image_url": image_url, "pdf_url": pdf_url}
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating summary.")

# Ask a Question
class AskQuestionRequest(BaseModel):
    title: str
    question: str

@app.post("/ask")
async def ask_question(request: AskQuestionRequest):
    try:
        if llama_index is None:
            logging.error("llama_index is not initialized.")
            raise HTTPException(status_code=500, detail="Service not initialized.")
        
        title = request.title
        question = request.question
        query_engine = llama_index.as_query_engine(similarity_top_k=5, streaming=False)
        response = query_engine.query(question)

        if response is None:
            raise HTTPException(status_code=500, detail="No response from the query engine.")

        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT IMAGE_URL, PDF_URL FROM PUBLICATIONS_METADATA WHERE TITLE = %s;", (title,))
        row = cursor.fetchone()
        image_url = row[0] if row else None
        pdf_url = row[1] if row else None
        cursor.close()
        conn.close()

        answer = response.response if hasattr(response, 'response') else str(response)
        formatted_answer = f"**Research Note**: {answer}\n\n"
        
        return {"answer": formatted_answer, "image_url": image_url, "pdf_url": pdf_url}
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the question.")
