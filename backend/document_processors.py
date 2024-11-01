import os
import boto3
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv
from llama_index.core.schema import Document

# Initialize S3 client
def init_s3():
    load_dotenv()
    bucket_name = os.getenv('AWS_BUCKET')
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    return s3, bucket_name

# Retrieve all PDF documents in /pdfs folder from S3 bucket
def get_all_pdf_documents():
    """Retrieve all PDF files from the /pdfs folder in S3 and extract text."""
    s3, bucket_name = init_s3()
    all_pdf_documents = []

    # 列出 /pdfs 資料夾中的所有 PDF 文件
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix="pdfs/")
    pdf_files = [content['Key'] for content in response.get('Contents', []) if content['Key'].endswith('.pdf')]

    # 處理每一個 PDF 文件
    for s3_key in pdf_files:
        try:
            pdf_obj = s3.get_object(Bucket=bucket_name, Key=s3_key)
            
            # 將 PDF 內容讀取為 BytesIO，讓 PyPDF2 能處理
            pdf_content = pdf_obj['Body'].read()
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # 合併整個 PDF 文件的文字內容
            full_text = ""
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"  # 每頁內容換行加入
            
            # 將合併後的文字內容存成一個 Document
            text_doc = Document(
                text=full_text,
                metadata={
                    "type": "text",
                    "source": s3_key
                },
                id_=s3_key
            )
            all_pdf_documents.append(text_doc)
            print(f"Processed document {s3_key}")

        except Exception as e:
            print(f"Error opening or processing the PDF file from S3 ({s3_key}): {e}")

    return all_pdf_documents
