from google.cloud import storage
import io
import datetime
from .config import GCS_BUCKET_NAME

def get_storage_client():
    """
    Initializes and returns a Google Cloud Storage client.
    Requires GOOGLE_APPLICATION_CREDENTIALS in environment if not using default auth.
    """
    return storage.Client()

def list_gcs_files():
    """
    Returns a list of all object names (files) in the configured GCS bucket.
    """
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    prefix = "amal_gopi/rag_app_hr_policy/"
    blobs = bucket.list_blobs(prefix=prefix)
    # Filter out "directories" if there are zero-byte files ending in /
    return [blob.name for blob in blobs if not blob.name.endswith('/')]

def get_gcs_file_in_memory(file_name):
    """
    Downloads a file from the configured GCS bucket into memory.
    Returns:
        io.BytesIO: The in-memory file stream.
    """
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(file_name)
    
    file_bytes = blob.download_as_bytes()
    return io.BytesIO(file_bytes)

def get_gcs_url(file_name, page=None):
    """
    Returns a URL for the given GCS file path.
    Tries to generate a signed URL (private buckets).
    Falls back to a public URL if signing fails.
    Appends page hash if provided.
    """
    if not file_name:
        return "#"
        
    client = get_storage_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(file_name)
    
    url = None
    try:
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET",
        )
    except Exception as e:
        print(f"Warning: Failed to generate signed URL for {file_name}: {e}")
        # Build the public accessible URL
        url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{file_name}"
        
    if page:
        url = f"{url}#page={page}"
        
    return url
