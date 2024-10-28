# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pinecone import Pinecone, Index , ServerlessSpec
import snowflake.connector
import os
from dotenv import load_dotenv
import requests
import boto3
from botocore.client import Config
from urllib.parse import urlparse
from langchain_nvidia_ai_endpoints import ChatNVIDIA,NVIDIAEmbeddings
import logging

# Load environment variables
load_dotenv()

app = FastAPI()

nvidia_api_key = os.getenv("NVIDIA_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_project_id = os.getenv("PINECONE_PROJECT_ID")

# Initialize Snowflake connection
def init_snowflake():
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
    )
    return conn

# Initialize Pinecone
def init_pinecone():
    # Initialize Pinecone client
    print("PINECONE_API_KEY:", pinecone_api_key)
    print("PINECONE_HOST:", os.getenv("PINECONE_HOST"))

    pinecone_client = Pinecone(api_key=pinecone_api_key)

    # Define the index name
    index_name = 'research-notes'  # Ensure this matches the index you created

    # Retrieve the host URL for the index from an environment variable or Pinecone dashboard
    index_host = os.getenv('PINECONE_HOST')

    # List available indexes
    available_indexes = [index.name for index in pinecone_client.list_indexes()]
    print("Available indexes:", available_indexes)

    # Check if the index exists, create if it doesn't
    if index_name not in available_indexes:
        pinecone_client.create_index(
            name=index_name,
            dimension=1024,  # Replace with your model dimensions
            metric="cosine",  # Replace with your model metric
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )

    # Connect to the existing index using the Index class with the host argument
    index = Index(index_name, host=index_host)
    return index

# Define data models
class Document(BaseModel):
    title: str
    summary: str
    image_url: str
    pdf_url: str

class Query(BaseModel):
    title: str  # Use document title as identifier
    question: str

class ResearchNote(BaseModel):
    title: str  # Use document title as identifier
    note_text: str

# Get list of documents
@app.get("/documents")
def get_documents():
    conn = init_snowflake()
    cursor = conn.cursor()
    cursor.execute("SELECT TITLE FROM PUBLICATIONS_METADATA;")
    rows = cursor.fetchall()
    documents = [{"title": row[0]} for row in rows]
    cursor.close()
    conn.close()
    return documents

# Get document details
@app.get("/documents/{title}")
def get_document_details(title: str):
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
    else:
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
    except Exception as e:
        print(f"Error generating pre-signed URL for image: {e}")
        document['image_url'] = None

    try:
        pdf_key = get_s3_object_key(document['pdf_url'])
        pdf_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': pdf_key},
            ExpiresIn=3600
        )
        document['pdf_url'] = pdf_url
    except Exception as e:
        print(f"Error generating pre-signed URL for PDF: {e}")
        document['pdf_url'] = None

    return document

# Submit a user question and return an answer
@app.post("/ask")
def ask_question(query: Query):
    try:
        # Retrieve vector embeddings for research notes
        index = init_pinecone()
        
        # Convert user question to vector
        question_embedding = get_embedding(query.question)
        
        # Perform similarity query in Pinecone
        results = index.query(
            vector=question_embedding,
            top_k=50,
            include_metadata=True
        )

        # Filter notes relevant to the document
        related_notes = []
        for match in results['matches']:
            if match['metadata']['title'] == query.title:
                related_notes.append(match['metadata']['note_text'])
                if len(related_notes) >= 5:
                    break  # Limit to the top 5 related notes

        # Generate answer using NVIDIA model
        answer = generate_answer_with_nvidia_model(query.question, related_notes, nvidia_api_key)
        return {"answer": answer}

    except Exception as e:
        logging.error(f"Error processing question: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the question.")

# Save research note
@app.post("/save_note")
def save_research_note(note: ResearchNote):
    conn = init_snowflake()
    cursor = conn.cursor()
    query = """
    INSERT INTO RESEARCH_NOTES (TITLE, NOTE_TEXT)
    VALUES (%s, %s);
    """
    cursor.execute(query, (note.title, note.note_text))
    conn.commit()
    cursor.close()
    conn.close()
    # Vectorize note and store in Pinecone
    index = init_pinecone()
    note_embedding = get_embedding(note.note_text)
    # Use a unique ID, e.g., combining title and a random note_id
    note_id = f"{note.title}_{os.urandom(8).hex()}"
    index.upsert(
        vectors=[(note_id, note_embedding, {'title': note.title, 'note_text': note.note_text})]
    )
    return {"status": "success"}

# Helper function: Get text embeddings
def get_embedding(text):
    # Initialize the NVIDIA embeddings client
    client = NVIDIAEmbeddings(
        model="nvidia/llama-3.2-nv-embedqa-1b-v1", 
        api_key=os.getenv('NVIDIA_API_KEY'),  # Load API key from environment variable
        truncate="NONE"
    )

    # Generate the embedding for the input text
    embedding = client.embed_query(text)
    
    return embedding

# Helper function: Generate answer using NVIDIA model
def generate_answer_with_nvidia_model(question, context_list, api_key):
    # Initialize the NVIDIA model client
    client = ChatNVIDIA(
        model="meta/llama-3.2-3b-instruct",
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

    return answer.strip()
