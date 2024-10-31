








# import os
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# import snowflake.connector
# from dotenv import load_dotenv
# import boto3
# from botocore.client import Config
# from urllib.parse import urlparse
# import logging
# from contextlib import asynccontextmanager

# # Import llama_index components
# from llama_index.core import Settings
# from llama_index.core import VectorStoreIndex, StorageContext
# from llama_index.core.node_parser import SentenceSplitter
# from llama_index.vector_stores.pinecone import PineconeVectorStore
# from llama_index.embeddings.nvidia import NVIDIAEmbedding
# from llama_index.llms.nvidia import NVIDIA

# from pinecone import Pinecone
# from llama_index.core.schema import Document as LlamaDocument

# # Load environment variables
# load_dotenv()

# # Configure logging with timestamps and levels
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[logging.StreamHandler()]
# )

# app = FastAPI()

# # Global variable to hold the index
# llama_index = None

# # Initialize Snowflake connection
# def init_snowflake():
#     try:
#         conn = snowflake.connector.connect(
#             user=os.getenv('SNOWFLAKE_USER'),
#             password=os.getenv('SNOWFLAKE_PASSWORD'),
#             account=os.getenv('SNOWFLAKE_ACCOUNT'),
#             warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
#             database=os.getenv('SNOWFLAKE_DATABASE'),
#             schema=os.getenv('SNOWFLAKE_SCHEMA'),
#         )
#         logging.info("Connected to Snowflake successfully.")
#         return conn
#     except Exception as e:
#         logging.error(f"Failed to connect to Snowflake: {e}")
#         raise

# # Initialize llama_index Settings
# def initialize_llama_index_settings():
#     Settings.embed_model = NVIDIAEmbedding(
#         model="nvidia/nv-embedqa-e5-v5", 
#         truncate="END",
#         api_key=os.getenv("NVIDIA_API_KEY")
#     )
#     Settings.llm = NVIDIA(
#         model="meta/llama-3.2-3b-instruct",
#         api_key=os.getenv("NVIDIA_API_KEY")
#     )
#     Settings.text_splitter = SentenceSplitter(chunk_size=600)
#     logging.info("llama_index settings initialized successfully.")

# # Initialize Pinecone connection
# def initialize_pinecone_connection():
#     try:
#         Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment=os.getenv("PINECONE_ENV"))
#         logging.info("Connected to Pinecone successfully.")
#     except Exception as e:
#         logging.error(f"Failed to connect to Pinecone: {e}")
#         raise

# # Create and initialize the index using llama_index with Pinecone
# def create_llama_index(documents):
#     try:
#         vector_store = PineconeVectorStore(
#             index_name=os.getenv("PINECONE_INDEX_NAME"),
#             dimension=768
#         )
#         logging.info("PineconeVectorStore initialized successfully.")

#         storage_context = StorageContext.from_defaults(vector_store=vector_store)

#         index = VectorStoreIndex.from_documents(
#             documents,
#             storage_context=storage_context
#         )
#         logging.info("VectorStoreIndex created successfully with Pinecone.")
#         logging.info(f"Total documents indexed: {len(documents)}")
        
#         return index
#     except Exception as e:
#         logging.error(f"Failed to create VectorStoreIndex with Pinecone: {e}")
#         raise

# # Load documents from Snowflake
# def load_documents_from_snowflake():
#     try:
#         conn = init_snowflake()
#         cursor = conn.cursor()
#         cursor.execute("SELECT TITLE, NOTE_TEXT FROM RESEARCH_NOTES;")
#         rows = cursor.fetchall()
#         documents = [
#             LlamaDocument(
#                 doc_id=row[0],
#                 text=row[1],
#                 metadata={"title": row[0]}
#             )
#             for row in rows
#         ]
#         cursor.close()
#         conn.close()
#         logging.info(f"Loaded {len(documents)} documents from Snowflake.")
#         return documents
#     except Exception as e:
#         logging.error(f"Error loading documents from Snowflake: {e}")
#         raise

# # Lifespan Event Handler
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     global llama_index
#     try:
#         initialize_pinecone_connection()
#         initialize_llama_index_settings()
#         documents = load_documents_from_snowflake()
#         llama_index = create_llama_index(documents)
#         yield
#     finally:
#         if llama_index:
#             del llama_index
#         logging.info("Application shutdown complete.")

# # Attach the lifespan to the FastAPI app
# app = FastAPI(lifespan=lifespan)

# # Define data models
# class DocumentRequest(BaseModel):
#     title: str

# class Query(BaseModel):
#     question: str

# class ResearchNoteRequest(BaseModel):
#     title: str
#     note_text: str

# class ResearchNoteSearchRequest(BaseModel):
#     title: str
#     query: str

# class ModifiedAnswerRequest(BaseModel):
#     title: str
#     modified_answer: str

# # Explore Documents API
# @app.get("/documents")
# async def get_documents():
#     try:
#         conn = init_snowflake()
#         cursor = conn.cursor()
#         cursor.execute("SELECT TITLE, PDF_URL FROM PUBLICATIONS_METADATA;")
#         rows = cursor.fetchall()
#         documents = [{"title": row[0], "pdf_url": row[1]} for row in rows]
#         cursor.close()
#         conn.close()
#         logging.info(f"Retrieved {len(documents)} documents.")
#         return documents
#     except Exception as e:
#         logging.error(f"Error retrieving documents: {e}")
#         raise HTTPException(status_code=500, detail="An error occurred while retrieving documents.")

# @app.get("/documents/{title}/summary")
# async def generate_summary(title: str):
#     try:
#         # 连接到 Snowflake 并检索文档的实际摘要
#         conn = init_snowflake()
#         cursor = conn.cursor()
        
#         # 假设在数据库中有一个 `SUMMARY` 字段，存储每个文档的摘要
#         cursor.execute("SELECT SUMMARY FROM PUBLICATIONS_METADATA WHERE TITLE = %s;", (title,))
#         row = cursor.fetchone()
        
#         if row and row[0]:  # 检查摘要是否存在
#             summary = row[0]
#         else:
#             summary = "No summary available for this document."
        
#         cursor.close()
#         conn.close()
        
#         return {"summary": summary}
#     except Exception as e:
#         logging.error(f"Error generating summary: {e}")
#         raise HTTPException(status_code=500, detail="An error occurred while generating summary.")
    


# # Question and Answer API with Report Generation
# @app.post("/ask")
# async def ask_question(query: Query):
#     try:
#         if llama_index is None:
#             logging.error("llama_index is not initialized.")
#             raise HTTPException(status_code=500, detail="Service not initialized.")
        
#         query_engine = llama_index.as_query_engine(similarity_top_k=5, streaming=False)
#         response = query_engine.query(query.question)

#         if response is None:
#             raise HTTPException(status_code=500, detail="No response from the query engine.")

#         answer = response.response if hasattr(response, 'response') else str(response)
#         formatted_answer = f"**Research Note**: {answer}\n\n[Related Graphs, Tables, and Pages](#)"
        
#         return {"answer": formatted_answer}
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         logging.error(f"Error processing question: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="An error occurred while processing the question.")

# # Save Modified Answer API
# @app.post("/save_modified_answer")
# async def save_modified_answer(request: ModifiedAnswerRequest):
#     try:
#         conn = init_snowflake()
#         cursor = conn.cursor()
#         insert_query = "INSERT INTO RESEARCH_NOTES (TITLE, NOTE_TEXT) VALUES (%s, %s);"
#         cursor.execute(insert_query, (request.title, request.modified_answer))
#         conn.commit()
#         cursor.close()
#         conn.close()
#         logging.info(f"Modified answer saved as research note for document '{request.title}'.")
        
#         new_document = LlamaDocument(
#             doc_id=request.title,
#             text=request.modified_answer,
#             metadata={"title": request.title}
#         )
#         llama_index.insert(new_document)
#         logging.info(f"Modified answer inserted into llama_index for document '{request.title}'.")
        
#         return {"status": "Modified answer saved successfully"}
#     except Exception as e:
#         logging.error(f"Error saving modified answer: {e}")
#         raise HTTPException(status_code=500, detail="An error occurred while saving the modified answer.")





























import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import snowflake.connector
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager

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
        logging.info("PineconeVectorStore initialized successfully.")

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

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

# Load documents from Snowflake
def load_documents_from_snowflake():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT TITLE, NOTE_TEXT FROM RESEARCH_NOTES;")
        rows = cursor.fetchall()
        documents = [
            LlamaDocument(
                doc_id=row[0],
                text=row[1],
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

# Define data models
class AskQuestionRequest(BaseModel):
    title: str
    question: str

class ModifiedAnswerRequest(BaseModel):
    title: str
    modified_answer: str

# Explore Documents API
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

@app.get("/documents/{title}/summary")
async def generate_summary(title: str):
    try:
        # Retrieve the document summary, image URL, and PDF URL from Snowflake
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

# Question and Answer API
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

        # Retrieve URL information for the document
        conn = init_snowflake()
        cursor = conn.cursor()
        cursor.execute("SELECT IMAGE_URL, PDF_URL FROM PUBLICATIONS_METADATA WHERE TITLE = %s;", (title,))
        row = cursor.fetchone()
        
        image_url = row[0] if row else None
        pdf_url = row[1] if row else None
        cursor.close()
        conn.close()

        # Format the generated answer with URLs
        answer = response.response if hasattr(response, 'response') else str(response)
        formatted_answer = f"**Research Note**: {answer}\n\n"
        if image_url:
            formatted_answer += f"[Document Image]({image_url})\n\n"
        if pdf_url:
            formatted_answer += f"[Download PDF]({pdf_url})"
        
        return {"answer": formatted_answer, "image_url": image_url, "pdf_url": pdf_url}
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the question.")

# Save Modified Answer API
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
        
        new_document = LlamaDocument(
            doc_id=request.title,
            text=request.modified_answer,
            metadata={"title": request.title}
        )
        llama_index.insert(new_document)
        logging.info(f"Modified answer inserted into llama_index for document '{request.title}'.")
        
        return {"status": "Modified answer saved successfully"}
    except Exception as e:
        logging.error(f"Error saving modified answer: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while saving the modified answer.")