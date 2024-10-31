import os
import snowflake.connector
from dotenv import load_dotenv
from pinecone import Pinecone, Index, ServerlessSpec
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# 加载环境变量
load_dotenv()

# 配置API密钥和其他连接信息
nvidia_api_key = os.getenv("NVIDIA_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_project_id = os.getenv("PINECONE_PROJECT_ID")
pinecone_host = os.getenv("PINECONE_HOST")

def test_pinecone_connection():
    print("Testing Pinecone connection...")
    try:
        # 初始化 Pinecone 客户端
        pinecone_client = Pinecone(api_key=pinecone_api_key)
        
        # 列出可用的索引
        indexes = [index.name for index in pinecone_client.list_indexes()]
        print("Available Pinecone indexes:", indexes)
        
        # 检查特定索引是否存在
        index_name = 'research-notes'
        if index_name in indexes:
            index = Index(index_name, host=pinecone_host)
            print(f"Connected to Pinecone index '{index_name}'.")
        else:
            print(f"Pinecone index '{index_name}' does not exist. Please create it in the Pinecone console.")
        
    except Exception as e:
        print("Failed to connect to Pinecone:", e)

def test_snowflake_connection():
    print("\nTesting Snowflake connection...")
    try:
        conn = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
        )
        
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print("Tables in Snowflake database:", tables)
        
        cursor.close()
        conn.close()
        print("Snowflake connection test successful.")
    except Exception as e:
        print("Failed to connect to Snowflake:", e)

def test_nvidia_embeddings():
    print("\nTesting NVIDIA Embeddings API...")
    try:
        client = NVIDIAEmbeddings(
            model="nvidia/llama-3.2-nv-embedqa-1b-v1",
            api_key=nvidia_api_key,
            truncate="NONE"
        )
        
        # 创建一个简单的测试嵌入
        text = "This is a test for NVIDIA Embeddings API."
        embedding = client.embed_query(text)
        print("Embedding generated successfully:", embedding[:10], "...")  # 只打印嵌入的前10个数值
        
    except Exception as e:
        print("Failed to connect to NVIDIA Embeddings API:", e)

if __name__ == "__main__":
    print("Running backend connection tests...\n")
    test_pinecone_connection()
    test_snowflake_connection()
    test_nvidia_embeddings()