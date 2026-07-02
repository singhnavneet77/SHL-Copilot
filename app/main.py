"""
FastAPI application for SHL Assessment Recommendation Agent
Endpoints: GET /health, POST /chat
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import ChatRequest, ChatResponse
from .agent import process_chat
from .retriever import build_index, load_catalog


# ─────────────────────────────────────────────
# Startup: Pre-load models
# ─────────────────────────────────────────────

_index_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build retrieval index on startup"""
    global _index_ready
    print("Initializing SHL Assessment Agent...")
    print("Loading catalog and building search index...")
    
    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, build_index)
    
    catalog = load_catalog()
    print(f"Ready! Indexed {len(catalog)} SHL assessments.")
    _index_ready = True
    
    yield
    
    print("Shutting down...")


# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="SHL Assessment Recommendation Agent",
    description="Conversational agent for recommending SHL Individual Test Solutions",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

# Serve static files (HTML/CSS/JS frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/")
async def root():
    """Serve the conversational web interface"""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to SHL Assessment Recommendation Agent API! Go to /docs for interactive documentation."}


@app.get("/health")
async def health():
    """
    Health check endpoint.
    Returns OK once the index is built (may take up to 2 minutes on cold start).
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Stateless conversational endpoint.
    
    Accepts full conversation history, returns next agent reply
    with optional structured shortlist of SHL assessment recommendations.
    
    Rules:
    - messages must have at least 1 entry
    - last message must be from 'user'
    - max 8 total turns recommended
    """
    # Validate request
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    
    if request.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="last message must be from user")
    
    # Cap check
    if len(request.messages) > 20:
        raise HTTPException(status_code=400, detail="conversation history too long")
    
    try:
        response = await process_chat(request.messages)
        return response
    except Exception as e:
        print(f"Agent error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
        )


@app.get("/catalog/count")
async def catalog_count():
    """Debug endpoint: returns catalog size"""
    catalog = load_catalog()
    return {"count": len(catalog)}
