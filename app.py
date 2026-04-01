import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

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
    sources: list[str]
    timestamp: str

# API Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Check if first query and pass down
        is_first = app.state.is_first_query
        
        # Execute RAG
        answer, sources, timestamp = query_rag(request.query, first_query=is_first)
        
        # Mark first query as done
        if is_first:
            app.state.is_first_query = False
            
        return ChatResponse(
            answer=answer,
            sources=sources,
            timestamp=timestamp
        )
    except Exception as e:
        print(f"Error handling query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    is_first = app.state.is_first_query
    if is_first:
        app.state.is_first_query = False

    def event_stream():
        try:
            for line in stream_rag(request.query, first_query=is_first):
                yield line
        except Exception as e:
            error_payload = json.dumps({"type": "error", "message": str(e)}) + "\n"
            yield error_payload

    return StreamingResponse(event_stream(), media_type="text/event-stream")

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
