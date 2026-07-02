---
title: SHL Assessment Recommendation Agent
emoji: 🤖
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
---

# SHL Assessment Recommendation Agent


## Setup & Run Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Scrape the SHL Catalog
```bash
python scrape_catalog.py
```

### 3. Set Your Gemini API Key
Get a free API key from https://aistudio.google.com/app/apikey
```bash
# Windows PowerShell:
$env:GEMINI_API_KEY = "your_key_here"

# OR create a .env file:
echo "GEMINI_API_KEY=your_key_here" > .env
```

### 4. Run the Server
```bash
python run.py
```
Or directly:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Test the API

**Health check:**
```bash
curl http://localhost:8000/health
```

**Chat example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "I need to hire a Java developer"}]}'
```

### 6. Run Tests
```bash
python test_agent.py
python test_retriever.py
```

## Project Structure
```
SHL/
├── app/
│   ├── main.py          # FastAPI app
│   ├── agent.py         # Conversation agent
│   ├── retriever.py     # Hybrid BM25+FAISS retrieval
│   ├── prompts.py       # LLM prompt templates
│   └── models.py        # Pydantic schemas
├── data/
│   └── catalog.json     # Scraped SHL catalog (234 products)
├── scrape_catalog.py    # Re-scrape catalog
├── requirements.txt
├── run.py               # Server entry point
└── approach_document.md # Submission document
```

## API Reference

### GET /health
Returns `{"status": "ok"}` when ready.

### POST /chat
**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hiring a Java developer"},
    {"role": "assistant", "content": "What is their seniority?"},
    {"role": "user", "content": "Mid-level, 4 years experience"}
  ]
}
```

**Response:**
```json
{
  "reply": "Based on your needs, here are 5 relevant SHL assessments...",
  "recommendations": [
    {"name": "Java 8 (New)", "url": "https://www.shl.com/...", "test_type": "K"},
    {"name": "OPQ32r", "url": "https://www.shl.com/...", "test_type": "P"}
  ],
  "end_of_conversation": false
}
```
