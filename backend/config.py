import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# The path to the Service Account JSON key is expected to be in GOOGLE_APPLICATION_CREDENTIALS
# which is automatically picked up by the google-cloud-storage library.

# Local directory where ChromaDB will persist its vector store
CHROMA_PERSIST_DIRECTORY = "./chroma_db"

def validate_config():
    missing_keys = []
    if not GOOGLE_API_KEY:
        missing_keys.append("GOOGLE_API_KEY")
    if not GCS_BUCKET_NAME:
        missing_keys.append("GCS_BUCKET_NAME")
    
    # We won't strictly validate GOOGLE_APPLICATION_CREDENTIALS here since default credentials might be used
    # depending on the environment.

    if missing_keys:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")
