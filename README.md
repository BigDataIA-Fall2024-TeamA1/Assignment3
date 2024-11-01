# AI-Driven Document Management System: End-to-End Automation and Research Insights

## Overview

The AI-Driven Document Management System is a comprehensive, automated solution for managing, analyzing, and extracting data from research publications. Designed for scalability and efficiency, this project incorporates automated data scraping, storage, analysis, and user interaction capabilities, using cloud-based tools and advanced AI technologies. The system features Apache Airflow for automated workflows, FastAPI as the backend service, and Streamlit for the client-facing interface. The entire system is containerized using Docker Compose, enabling seamless deployment, scaling, and accessibility.

## Attestation and Contribution Declaration

WE ATTEST THAT WE HAVEN'T USED ANY OTHER STUDENTS' WORK IN OUR ASSIGNMENT AND ABIDE BY THE POLICIES LISTED IN THE STUDENT HANDBOOK.

**Contribution Breakdown**:
- Chiu Meng Che: 34%
- Shraddha Bhandarkar: 33%
- Kefan Zhang: 33%

## Workflow Diagram

![workflow](images/workflow_diagram.jpeg)

The workflow diagram outlines the integration of major components including Apache Airflow, Streamlit, FastAPI, Amazon S3, Docker, and Pinecone. Documents are initially retrieved from the CFA Institute and stored in Amazon S3. Apache Airflow orchestrates the automated retrieval and processing pipeline. FastAPI serves as the middleware to facilitate the interaction between the Streamlit interface and backend services such as document processing, embedding models, and Pinecone for indexing. Docker is utilized to containerize each module to ensure a consistent and reliable deployment.

## Key Features

### **Automated Document Processing and Storage**
- **Data Scraping**: Apache Airflow automates the extraction of document data from the CFA Institute, including metadata, PDF files, and summaries.
- **Cloud Storage**: Extracted documents are uploaded and stored in Amazon S3 for secure and scalable storage.

### **Backend API with FastAPI**
- **Document Exploration**: Provides REST API endpoints to explore documents and their content, including metadata, summaries, and links.
- **Q/A Interface**: Allows users to interact with documents by posing queries, which are processed using AI models to extract insightful answers.
- **Embedding with Pinecone**: Utilizes Pinecone for storing document embeddings, enabling fast and efficient similarity searches.

### **User Interface with Streamlit**
- **Document Interaction**: A clean, intuitive UI for users to register, upload, and interact with documents. Users can query documents, explore extracted data, and generate custom research notes.
- **Authentication**: Provides secure user login and registration managed via an integrated PostgreSQL database.

### **AI-Powered Insights**
- **Multi-modal RAG Integration**: Supports Retrieval-Augmented Generation (RAG) for in-depth content analysis and dynamic answers to research questions.
- **Document Summarization**: NVIDIA-powered AI models generate concise and informative summaries to help users quickly understand document content.

### **Containerized Deployment**
- **Docker Compose Setup**: The entire project is containerized using Docker Compose, which ensures that all services (frontend, backend, pipeline) work seamlessly together and are easy to deploy.
- **Scalable Architecture**: Containerization allows for easy scaling and cloud deployment, providing reliability and flexibility.

## Project Structure

```bash
│  .env
│  .gitignore
│  project_tree_structure
│  
├── airflow
│   │  airflow.cfg
│   │  poetry.lock
│   │  pyproject.toml
│   └── dags
│       ├── pipeline.py
│       └── modules
│           ├── cfa_scrape_data.py
│           └── __init__.py
├── backend
│   │  delete_vector.py
│   │  document_processors.py
│   │  insert_vector.py
│   │  main.py
│   │  poetry.lock
│   └── pyproject.toml
├── frontend
│   │  poetry.lock
│   │  pyproject.toml
│   │  streamlit_app.py
└── images
        workflow_diagram.jpeg
```

## Prerequisites

**Docker**: Required to containerize and run the application services.
- [Download and Install Docker](https://www.docker.com/get-started)
- Verify installation:
  ```bash
  docker --version
  ```

**Docker Compose**: To manage the multi-container setup.
- Verify installation:
  ```bash
  docker-compose --version
  ```

**Poetry**: A Python dependency management tool.
- Install Poetry by following the instructions: [Poetry Installation Guide](https://python-poetry.org/docs/#installation)
- Verify installation:
  ```bash
  poetry --version
  ```

**Python 3.9+**: The project requires Python 3.9 or above.
- Verify installation:
  ```bash
  python3 --version
  ```

Ensure all prerequisites are installed before proceeding to deployment.

## Installation and Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your_repository/ai-driven-document-system.git
   cd ai-driven-document-system
   ```

2. **Environment Setup**
   - Use Poetry to install all dependencies:
     ```bash
     poetry install
     ```

3. **Running the Application with Docker Compose**
   - Start the entire system:
     ```bash
     docker-compose up --build
     ```
   - This command will spin up all required containers including Airflow, FastAPI, and Streamlit services.

4. **Access the Application**
   - Streamlit frontend is accessible at `http://localhost:8501`
   - FastAPI backend documentation (Swagger UI) is available at `http://localhost:8000/docs`

## Contributions and Time Breakdown

**Chiu Meng Che**:
1. Created workflow diagrams illustrating the interaction between different components, such as Streamlit, FastAPI, Airflow, S3, and Pinecone. *(3 hours)*
2. Developed Airflow DAGs to automate document ingestion and cloud storage in AWS S3. *(1.5 days)*
3. Set up Dockerfiles for containerization and implemented Docker Compose for deployment. *(2 days)*
4. Authored the initial README and improved documentation clarity. *(1.5 hours)*

**Shraddha Bhandarkar**:
1. Integrated Azure Form Recognizer for extracting structured data from documents. *(3 days)*
2. Implemented PyMuPDF for local PDF processing as an alternative to cloud services. *(8 hours)*
3. Enhanced the Streamlit interface for smoother user experience and better data representation. *(10 hours)*

**Kefan Zhang**:
1. Developed FastAPI backend to handle API requests, integrating S3, Pinecone, and user authentication. *(30 hours)*
2. Deployed the application on AWS EC2, conducting end-to-end testing and validation. *(4 hours)*
3. Built additional functionality in Streamlit for better integration with backend services. *(16 hours)*

## Resources

- **LLAMA Multimodal Report Generation Example**
- **NVIDIA Multimodal RAG Example**
- **Multimodal RAG Slide Deck Example**

## Demonstration Video

[Click here to watch the video demonstration](https://youtu.be/MyrS6RYSmA4)

## Codelabs Documentation

[Click here to view the Codelabs documentation](https://codelabs-preview.appspot.com/?file_id=YOUR_FILE_ID#0)


