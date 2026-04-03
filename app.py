import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import base64
import mimetypes
from fastapi import Query
from backend.gcs_manager import get_gcs_file_in_memory
import io
try:
    import fitz
except ImportError:
    fitz = None

# We must import validate_config to ensure environment is setup, but we do it gracefully
try:
    from backend.config import validate_config
    validate_config()
except Exception as e:
    print(f"Configuration Error: {e}")
    # In a real app we might sys.exit(1), but lets allow the server to start to show errors

from backend.rag import query_rag, stream_rag

app = FastAPI(title="HR Policy Chatbot")

# Global variables for tracking state
app.state.is_first_query = True

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    timestamp: str

# API Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Validate input
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Check if first query and pass down
        is_first = app.state.is_first_query
        
        try:
            # Execute RAG
            answer, sources, timestamp = query_rag(request.query, first_query=is_first)
        except Exception as rag_error:
            print(f"RAG execution error: {rag_error}")
            raise HTTPException(status_code=500, detail="Internal server error processing your query")
        
        # Mark first query as done
        if is_first:
            app.state.is_first_query = False
            
        return ChatResponse(
            answer=answer,
            sources=sources,
            timestamp=timestamp
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    try:
        # Validate input
        if not request.query or not request.query.strip():
            def empty_query_error():
                yield json.dumps({"type": "error", "message": "Query cannot be empty"}) + "\n"
            return StreamingResponse(empty_query_error(), media_type="text/event-stream")
        
        is_first = app.state.is_first_query
        if is_first:
            app.state.is_first_query = False

        def event_stream():
            try:
                for line in stream_rag(request.query, first_query=is_first):
                    yield line
            except Exception as e:
                print(f"Error in stream (masked from user): {e}")
                error_payload = json.dumps({"type": "error", "message": "Service error occurred"}) + "\n"
                yield error_payload

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        print(f"Unexpected error in chat stream endpoint: {e}")
        def error_response():
            yield json.dumps({"type": "error", "message": "Internal server error"}) + "\n"
        return StreamingResponse(error_response(), media_type="text/event-stream")

@app.get("/api/document")
async def serve_document(c: str = Query(...), search: str = Query(None)):
    try:
        file_path = base64.b64decode(c).decode('utf-8')
        file_stream = get_gcs_file_in_memory(file_path)
        
        # Determine mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        file_bytes = file_stream.read()
        
        # Add yellow highlight using PyMuPDF if it's a PDF and search phrase is provided
        if file_path.lower().endswith(".pdf") and search and fitz:
            try:
                search_phrase_full = base64.b64decode(search).decode('utf-8')
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                
                words = search_phrase_full.split()
                
                # Create overlapping 5-word rolling n-grams. This aggressively paints the chunk yellow and natively bypasses
                # any hyphens or line mismatches between PyPDF2 text extraction and PyMuPDF's spatial search engine
                phrases = []
                for i in range(len(words) - 4):
                    phrases.append(" ".join(words[i:i+5]))
                    
                if not phrases and words:
                    phrases.append(" ".join(words))
                
                for page in doc:
                    for phrase in phrases:
                        text_instances = page.search_for(phrase)
                        if text_instances:
                            for inst in text_instances:
                                annot = page.add_highlight_annot(inst)
                                annot.update()
                
                # Update file bytes with modified PDF
                file_bytes = doc.tobytes()
                doc.close()
            except Exception as e:
                print(f"Error highlighting PDF: {e}")
                
        output_stream = io.BytesIO(file_bytes)
        output_stream.seek(0)
        
        return StreamingResponse(
            output_stream, 
            media_type=mime_type, 
            headers={
                "Content-Disposition": f"inline; filename=\"{os.path.basename(file_path)}\"",
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"
            }
        )
    except Exception as e:
        print(f"Error serving document: {e}")
        raise HTTPException(status_code=404, detail="Document not found or inaccessible")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve UI
@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "index.html not found in static folder."}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
