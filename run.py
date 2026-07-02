"""
Entry point to run the FastAPI server
Usage: python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # Set to True for development
        workers=1,     # Single worker (shared FAISS index)
    )
