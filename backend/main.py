import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import snowflake.connector
from dotenv import load_dotenv
import boto3
from botocore.client import Config
from urllib.parse import urlparse
import logging
import time
from contextlib import asynccontextmanager

# Import llama_index components
from llama_index.core import Settings  # Updated import
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.nvidia import NVIDIAEmbedding
from llama_index.llms.nvidia import NVIDIA

from pinecone import Pinecone  # Import Pinecone client
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
        # Initialize Pinecone Vector Store
        vector_store = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            dimension=768  # Ensure this matches the embedding dimension
        )
        logging.info("PineconeVectorStore initialized successfully.")

        # Create StorageContext with the VectorStore
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Create VectorStoreIndex from documents using the storage_context
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context
        )
        logging.info("VectorStoreIndex created successfully with Pinecone.")
        logging.info(f"Total documents indexed: {len(documents)}")
        
        return index
    except Exception as e:
        logging.error(f"Failed to create VectorStoreIndex with Pinecone: {e}")
        raise


# Function to load documents from Snowflake
def load_documents_from_snowflake():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT TITLE, NOTE_TEXT FROM RESEARCH_NOTES;")
        rows = cursor.fetchall()
        documents = [
            LlamaDocument(
                doc_id=row[0],  # Assuming TITLE is unique and can serve as doc_id
                text=row[1],     # Changed from 'content' to 'text'
                metadata={"title": row[0]}
            )
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
        initialize_pinecone_connection()  # Initialize Pinecone connection first
        initialize_llama_index_settings()  # Configure LlamaIndex settings
        documents = load_documents_from_snowflake()  # Load documents from Snowflake
        llama_index = create_llama_index(documents)  # Create the index
        yield
    finally:
        # Shutdown actions (if any)
        if llama_index:
            # Perform any necessary cleanup for llama_index
            del llama_index
        logging.info("Application shutdown complete.")

# Attach the lifespan to the FastAPI app
app = FastAPI(lifespan=lifespan)

# Define data models
class ResearchDocument(BaseModel):
    title: str
    note_text: str

class Query(BaseModel):
    question: str  # Removed 'title' as it's unused

class ResearchNote(BaseModel):
    title: str  # Use document title as identifier
    note_text: str

# Get list of documents
@app.get("/documents")
async def get_documents():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT TITLE FROM PUBLICATIONS_METADATA;")
        rows = cursor.fetchall()
        documents = [{"title": row[0]} for row in rows]
        cursor.close()
        conn.close()
        logging.info(f"Retrieved {len(documents)} documents.")
        return documents
    except Exception as e:
        logging.error(f"Error retrieving documents: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving documents.")

# Get document details
@app.get("/documents/{title}")
async def get_document_details(title: str):
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        query = "SELECT TITLE, SUMMARY, IMAGE_URL, PDF_URL FROM PUBLICATIONS_METADATA WHERE TITLE = %s;"
        cursor.execute(query, (title,))
        row = cursor.fetchone()
        if row:
            document = {
                "title": row[0],
                "summary": row[1],
                "image_url": row[2],
                "pdf_url": row[3],
            }
            logging.info(f"Retrieved details for document '{title}'.")
        else:
            logging.warning(f"Document '{title}' not found.")
            raise HTTPException(status_code=404, detail="Document not found")
        cursor.close()
        conn.close()

        # Generate pre-signed URLs for image and PDF
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION'),
            config=Config(signature_version='s3v4')
        )
        bucket_name = os.getenv('AWS_BUCKET')

        # Extract object key from URL
        def get_s3_object_key(url):
            parsed_url = urlparse(url)
            # Remove leading '/' from the path
            object_key = parsed_url.path.lstrip('/')
            # Remove bucket name from path if included
            if object_key.startswith(bucket_name + '/'):
                object_key = object_key[len(bucket_name) + 1:]
            return object_key

        try:
            image_key = get_s3_object_key(document['image_url'])
            image_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': image_key},
                ExpiresIn=3600
            )
            document['image_url'] = image_url
            logging.info(f"Generated pre-signed URL for image of document '{title}'.")
        except Exception as e:
            logging.error(f"Error generating pre-signed URL for image: {e}")
            document['image_url'] = None

        try:
            pdf_key = get_s3_object_key(document['pdf_url'])
            pdf_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': pdf_key},
                ExpiresIn=3600
            )
            document['pdf_url'] = pdf_url
            logging.info(f"Generated pre-signed URL for PDF of document '{title}'.")
        except Exception as e:
            logging.error(f"Error generating pre-signed URL for PDF: {e}")
            document['pdf_url'] = None

        return document
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error retrieving document details: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving document details.")

# Submit a user question and return an answer
@app.post("/ask")
async def ask_question(query: Query):
    try:
        if llama_index is None:
            logging.error("llama_index is not initialized.")
            raise HTTPException(status_code=500, detail="Service not initialized.")
        
        # Use the globally initialized llama_index
        query_engine = llama_index.as_query_engine(similarity_top_k=5, streaming=False)
        logging.info(f"Executing query: {query.question}")

        response = query_engine.query(query.question)
        logging.info(f"Raw response from query engine: {response}")

        # Check if response is None or empty
        if response is None:
            logging.error("Received empty response from query engine.")
            raise HTTPException(status_code=500, detail="No response from the query engine.")

        # Extract the answer
        if hasattr(response, 'response'):
            answer = response.response
        else:
            answer = str(response)  # Fallback if 'response' attribute doesn't exist

        logging.info(f"Generated answer for question: {answer}")
        return {"answer": answer}

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the question.")

# Save research note
@app.post("/save_note")
async def save_research_note(note: ResearchNote):
    try:
        # Save note to Snowflake
        conn = init_snowflake()
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO RESEARCH_NOTES (TITLE, NOTE_TEXT)
        VALUES (%s, %s);
        """
        cursor.execute(insert_query, (note.title, note.note_text))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Saved research note for document '{note.title}' to Snowflake.")

        # Create a Document object
        new_document = LlamaDocument(
            doc_id=note.title,  # Ensure this is unique
            text=note.note_text,  
            metadata={"title": note.title}
        )

        # Insert the new document into the index
        llama_index.insert(new_document)
        logging.info(f"Inserted research note into llama_index for document '{note.title}'.")

        return {"status": "success"}
    except Exception as e:
        logging.error(f"Error saving research note: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while saving the research note.")


# Helper function: Get text embeddings (if needed)
# Note: With llama_index, embeddings are handled internally.
# However, if you still need direct access, you can define this function.

def get_embedding(text):
    try:
        # Initialize the NVIDIA embeddings client
        client = NVIDIAEmbedding(
            model="nvidia/nv-embedqa-e5-v5", 
            truncate="END"
        )

        # Generate the embedding for the input text
        embedding = client.embed(text)
        logging.info("Generated embedding for input text.")
        
        return embedding
    except Exception as e:
        logging.error(f"Error generating embedding: {e}")
        raise

# Helper function: Generate answer using NVIDIA model (if needed)
# Note: With llama_index's query engine, the answer generation is handled.
# However, if you still need direct access, you can define this function.

def generate_answer_with_nvidia_model(question, context_list, api_key):
    try:
        # Initialize the NVIDIA model client
        client = NVIDIA(
            model="meta/llama-3.1-70b-instruct",
            api_key=api_key, 
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
        )

        # Combine context_list into a single context string
        context = ' '.join(context_list)
        prompt = f"{context}\nQuestion: {question}\nAnswer:"

        # Stream the response from the model
        answer = ""
        for chunk in client.stream([{"role": "user", "content": prompt}]):
            answer += chunk.content

        answer = answer.strip()
        logging.info("Generated answer using NVIDIA model.")
        return answer
    except Exception as e:
        logging.error(f"Error generating answer with NVIDIA model: {e}")
        raise
