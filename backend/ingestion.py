import io
import PyPDF2
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from .config import CHROMA_PERSIST_DIRECTORY
from .gcs_manager import list_gcs_files, get_gcs_file_in_memory

def get_embeddings_model():
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

def get_chroma_db():
    embeddings = get_embeddings_model()
    return Chroma(
        persist_directory=CHROMA_PERSIST_DIRECTORY,
        embedding_function=embeddings
    )

def extract_text_from_bytes(file_bytes_io, file_name):
    """
    Extract text directly from memory. Handled formats: PDF, TXT.
    Returns a unified string of text.
    """
    text = ""
    if file_name.lower().endswith('.pdf'):
        try:
            reader = PyPDF2.PdfReader(file_bytes_io)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            print(f"Error parsing PDF {file_name}: {e}")
    elif file_name.lower().endswith('.txt'):
        text = file_bytes_io.read().decode('utf-8', errors='ignore')
    else:
        print(f"Unsupported file format for ingestion: {file_name}. Continuing...")
    return text

def ingest_new_documents():
    """
    Synchronizes documents. Checks Chroma for existing source files,
    compares with GCS, and only ingests the new ones directly from memory.
    """
    db = get_chroma_db()
    gcs_files = list_gcs_files()
    
    # Get existing documents in DB based on source metadata
    existing_docs = db.get(include=["metadatas"])
    existing_docs_metadata = existing_docs.get("metadatas", [])
    
    existing_sources = set()
    for meta in existing_docs_metadata:
        if isinstance(meta, dict) and "source" in meta:
            existing_sources.add(meta["source"])
            
    # Find files in GCS that are not in Chroma
    new_files_to_ingest = [f for f in gcs_files if f not in existing_sources]
    
    if not new_files_to_ingest:
        print("No new documents to ingest. DB is up to date.")
        return False
    
    print(f"Found {len(new_files_to_ingest)} new document(s) to ingest: {new_files_to_ingest}")
    
    docs_to_embed = []
    
    for file_name in new_files_to_ingest:
        print(f"Loading {file_name} directly from GCS to memory...")
        try:
            file_stream = get_gcs_file_in_memory(file_name)
            text = extract_text_from_bytes(file_stream, file_name)
            
            if text.strip():
                doc = Document(page_content=text, metadata={"source": file_name})
                docs_to_embed.append(doc)
        except Exception as e:
            print(f"Error processing {file_name}: {e}")
            
    if not docs_to_embed:
        print("No valid text extracted from new documents.")
        return False
        
    print("Chunking documents...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(docs_to_embed)
    
    print(f"Storing {len(split_docs)} chunks into ChromaDB...")
    db.add_documents(split_docs)
    
    print("Ingestion complete.")
    return True
