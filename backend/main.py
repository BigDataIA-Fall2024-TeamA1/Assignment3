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

# Import llama_index components
from llama_index.core import Settings
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.embeddings.nvidia import NVIDIAEmbedding
from llama_index.llms.nvidia import NVIDIA

from pymilvus import connections

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure logging with timestamps and levels
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Validate environment variables
required_env_vars = [
    "ZILLIZ_CLOUD_URI",
    "ZILLIZ_USERNAME",
    "ZILLIZ_PASSWORD",
    "ZILLIZ_COLLECTION_NAME",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "AWS_BUCKET",
    "NVIDIA_API_KEY",
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

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
        truncate="END"
    )
    Settings.llm = NVIDIA(
        model="meta/llama-3.1-70b-instruct"
    )
    Settings.text_splitter = SentenceSplitter(chunk_size=600)
    logging.info("llama_index settings initialized successfully.")

# 初始化连接到 Zilliz Cloud
def initialize_zilliz_connection():
    try:
        connections.connect(
            alias="default",
            uri=os.getenv("ZILLIZ_CLOUD_URI"),  # 例如 "ssl://<host>:<port>"
            user=os.getenv("ZILLIZ_USERNAME"),  # 如果需要
            password=os.getenv("ZILLIZ_PASSWORD")  # 如果需要
        )
        logging.info("Connected to Zilliz Cloud successfully.")
    except Exception as e:
        logging.error(f"Failed to connect to Zilliz Cloud: {e}")
        raise

# Create and initialize the index using llama_index
def create_llama_index(documents, service_context):
    try:
        # 初始化 ZillizCloudVectorStore
        vector_store = MilvusVectorStore(
            using="default",  # 使用上面连接的 alias
            collection_name=os.getenv("ZILLIZ_COLLECTION_NAME", "research_notes_collection"),
            dim=1024,
            index_type="IVF_FLAT",
            metric_type="L2",
            params={"nlist": 128}
        )
        logging.info("MilvusVectorStore initialized successfully with Zilliz Cloud.")
        
        # 创建 StorageContext
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # 创建 VectorStoreIndex 从文档
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            service_context=service_context
        )
        logging.info("VectorStoreIndex created successfully.")
        logging.info(f"Total documents indexed: {len(documents)}")
        
        return index
    except Exception as e:
        logging.error(f"Failed to create VectorStoreIndex: {e}")
        raise

# Function to load documents from Snowflake
def load_documents_from_snowflake():
    try:
        conn = init_snowflake()
        cursor = conn.cursor()
        # 修改后的 SQL 查询，仅选择存在的列
        cursor.execute("SELECT TITLE, NOTE_TEXT FROM RESEARCH_NOTES;")
        rows = cursor.fetchall()
        documents = []
        for row in rows:
            doc = {
                "title": row[0],
                "note_text": row[1]
            }
            documents.append(doc)
        cursor.close()
        conn.close()
        logging.info(f"Loaded {len(documents)} documents from Snowflake.")
        return documents
    except Exception as e:
        logging.error(f"Error loading documents from Snowflake: {e}")
        raise

# Function to keep the collection loaded (keep-alive)
# Function to keep the collection loaded (keep-alive)
def keep_collection_loaded(vector_store, interval=300):
    while True:
        try:
            if not vector_store.is_collection_loaded():
                vector_store.load_collection()
                logging.info(f"Collection '{vector_store.collection_name}' reloaded into memory (keep-alive).")
            else:
                logging.info(f"Collection '{vector_store.collection_name}' is already loaded.")
        except Exception as e:
            logging.error(f"Error in keep-alive for collection '{vector_store.collection_name}': {e}")
        time.sleep(interval)  # Wait for the specified interval before checking again


# Initialize llama_index and create indexF
def initialize_index():
    service_context = initialize_llama_index_settings()
    documents = load_documents_from_snowflake()
    index = create_llama_index(documents, service_context)
    return index


# Define data models
class Document(BaseModel):
    title: str
    note_text: str

class Query(BaseModel):
    title: str  # Use document title as identifier
    question: str

class ResearchNote(BaseModel):
    title: str  # Use document title as identifier
    note_text: str

# Initialize llama_index
llama_index = initialize_index()

# Get list of documents
@app.get("/documents")
def get_documents():
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
def get_document_details(title: str):
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
def ask_question(query: Query):
    try:
        # 使用 llama_index 的查询引擎
        query_engine = llama_index.as_query_engine(similarity_top_k=5, streaming=False)  # 设置 streaming=False 进行测试
        logging.info(f"Executing query: {query.question}")

        response = query_engine.query(query.question)  # 移除 filters 参数
        logging.info(f"Raw response from query engine: {response}")

        # 根据 llama_index 的响应结构提取答案
        # 假设 response 有一个 'response' 属性包含答案
        if hasattr(response, 'response'):
            answer = response.response
        else:
            answer = str(response)  # 备用方案

        logging.info(f"Generated answer for question on document '{query.title}': {answer}")
        return {"answer": answer}

    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the question.")


# Save research note
@app.post("/save_note")
def save_research_note(note: ResearchNote):
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

        # Vectorize note and store in llama_index
        # Create a document dictionary
        new_document = {
            "title": note.title,
            "note_text": note.note_text
        }

        # Add the new document to the index
        llama_index.insert_documents([new_document])
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
