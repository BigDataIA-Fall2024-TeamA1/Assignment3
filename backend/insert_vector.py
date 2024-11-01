# insert_vector.py
import os
from pinecone import Pinecone
from dotenv import load_dotenv
from llama_index.core import Settings  # Updated import
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.nvidia import NVIDIAEmbedding
from document_processors import get_all_pdf_documents
import logging

load_dotenv()

# 初始化 Pinecone 和嵌入模型
def initialize_pinecone_connection():
    try:
        Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment=os.getenv("PINECONE_ENV"))
        logging.info("Connected to Pinecone successfully.")
    except Exception as e:
        logging.error(f"Failed to connect to Pinecone: {e}")
        raise

def initialize_llama_index_settings():
    Settings.embed_model = NVIDIAEmbedding(
        model="nvidia/nv-embedqa-e5-v5", 
        truncate="END",
        api_key=os.getenv("NVIDIA_API_KEY")
    )
    Settings.text_splitter = SentenceSplitter(chunk_size=1500)
    logging.info("llama_index settings initialized successfully.")



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
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context
        )
        logging.info("VectorStoreIndex created successfully with Pinecone.")
        logging.info(f"Total documents indexed: {len(documents)}")
        
    except Exception as e:
        logging.error(f"Failed to create VectorStoreIndex with Pinecone: {e}")
        raise    

if __name__ == "__main__":
    # 假設 S3 keys 是一個包含所有 PDF 文件 S3 key 的清單
    initialize_pinecone_connection()
    initialize_llama_index_settings()
    documents = get_all_pdf_documents()
    create_llama_index(documents)