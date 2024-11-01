import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()
# 初始化 Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment=os.getenv("PINECONE_ENV"))

# 選擇 Index
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

# 刪除所有 vectors
index.delete(delete_all=True)
