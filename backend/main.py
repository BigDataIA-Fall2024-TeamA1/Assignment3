# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pinecone
import snowflake.connector
import os
from dotenv import load_dotenv
import requests
import boto3
from botocore.client import Config
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

app = FastAPI()

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
    pinecone.init(
        api_key=os.getenv('PINECONE_API_KEY'),
        environment=os.getenv('PINECONE_ENV')
    )

    index_name = 'research-notes'

    # Only connect to the existing index without attempting to create a new one
    if index_name in pinecone.list_indexes():
        index = pinecone.Index(index_name)
        return index
    else:
        # Raise an error if the index doesn't exist
        raise HTTPException(
            status_code=500,
            detail="Pinecone index 'research-notes' not found. Please create the index manually in your Pinecone console."
        )

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
    # Retrieve vector embeddings for research notes
    index = init_pinecone()
    # Convert user question to vector
    question_embedding = get_embedding(query.question)
    # Query relevant research notes for the document in Pinecone

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
    answer = generate_answer_with_nvidia_model(query.question, related_notes, None)
    return {"answer": answer}

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
    import nemo.collections.nlp as nemo_nlp
    import torch

    # 選擇預訓練的模型
    model_name = 'megatron-bert-345m-uncased'
    model = nemo_nlp.models.MegatronBertEncoderModel.from_pretrained(model_name)
    model.eval()

    # Tokenize the input text
    tokenizer = nemo_nlp.modules.get_tokenizer(tokenizer_name='bert-base-uncased')
    tokens = tokenizer(text, return_tensors='pt', truncation=True, max_length=512)

    # Move tensors to GPU if available
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    tokens = {k: v.to(device) for k, v in tokens.items()}
    model.to(device)

    with torch.no_grad():
        outputs = model(input_ids=tokens['input_ids'], attention_mask=tokens['attention_mask'])
        embeddings = outputs.last_hidden_state

    # 將 embeddings 轉換為一維的 numpy array
    embedding_vector = embeddings.mean(dim=1).squeeze().cpu().numpy()

    return embedding_vector.tolist()

# Helper function: Generate answer using NVIDIA model
def generate_answer_with_nvidia_model(question, context_list, api_key):
    import nemo.collections.nlp as nemo_nlp
    import torch

    # Combine context_list into a single context string
    context = ' '.join(context_list)
    prompt = f"{context}\nQuestion: {question}\nAnswer:"

    # Load the pre-trained GPT model for text generation
    model_name = 'gpt3-345m'
    model = nemo_nlp.models.GPTModel.from_pretrained(model_name)
    model.eval()

    # Move model to GPU if available
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)

    # Generate answer
    tokens_to_generate = 128
    input_tokens = model.tokenizer(prompt, return_tensors='pt')['input_ids'].to(device)

    with torch.no_grad():
        generated_tokens = model.generate(
            input_ids=input_tokens,
            max_length=input_tokens.shape[1] + tokens_to_generate,
            do_sample=True,
            top_k=50,
            top_p=0.95,
            temperature=0.7,
            num_return_sequences=1
        )

    # Decode the generated tokens
    generated_text = model.tokenizer.decode(generated_tokens[0], skip_special_tokens=True)

    # Extract the answer part from the generated text
    answer = generated_text[len(prompt):].strip()

    return answer
