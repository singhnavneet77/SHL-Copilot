# Approach Document: SHL Assessment Recommendation Agent

## Problem & Solution Summary

Hiring managers often cannot articulate exact assessment needs upfront — they start with vague intent ("I'm hiring a Java developer") and refine through dialogue. Standard keyword search catalogs fail here. This agent uses a conversational approach to guide users from vague intent to a grounded shortlist of SHL Individual Test Solutions.

## Architecture Overview

The system is a stateless FastAPI service with four layers:

**1. Safety Guard** — Regex-based detection of off-topic queries (salary, legal, prompt injection) with immediate refusal. Applied before any LLM call to minimize latency and prevent misuse.

**2. Hybrid Retrieval (BM25 + Semantic)** — The retrieval engine combines:
- BM25 (rank_bm25) for exact keyword matching — critical for technical test names like "Java 8", "Python 3.x", "SQL"
- FAISS dense retrieval with all-MiniLM-L6-v2 embeddings for semantic matching — catches conceptual matches like "works with stakeholders" → personality/behavioral assessments
- Score fusion: `0.4 × BM25_norm + 0.6 × semantic_norm`

**3. LLM Agent (Gemini 1.5 Flash)** — Four specialized prompts:
- Context extractor: Parses conversation into structured fields (role, seniority, domain, skills)
- Clarifier: Asks one focused question when context is insufficient
- Recommender: Selects 1–10 assessments from top-20 retrieved candidates
- Comparator: Grounds comparison in catalog data, not prior knowledge

**4. Schema Enforcement** — All recommendations are validated against the scraped catalog before returning. URLs are either hardcoded for known products or constructed from a slug pattern. The LLM cannot invent URLs.

## Catalog & Data

Source: `https://online.shl.com/gb/en-us/products?producttypes=1` (Individual Test Solutions)
- 234 products scraped via BeautifulSoup from the server-rendered HTML table
- Fields captured: name, description (up to 800 chars), languages, job levels, propositions, product types
- Test types inferred from content patterns (OPQ/personality → P, Java/SQL → K, numerical/verbal → A, etc.)
- URLs constructed as `/solutions/products/product-catalog/view/{slug}/` with hardcoded overrides for key products

## Conversation Design

The agent uses an implicit state machine:
1. **Turn 1 vague** → Always clarify (probe: "agent does not recommend on turn 1 for vague query")
2. **Context sufficient** → Recommend (at least job_role OR technical_domain + skills)
3. **≥3 clarifications asked** → Force recommendation (prevents getting stuck)
4. **Refinement detected** → Re-run retrieval with updated context, update shortlist
5. **Comparison detected** → Fetch catalog data for named products, compare grounded

Turn cap compliance: After 7 messages, the agent is forced to recommend regardless of context gaps.

## Evaluation Approach

Tested against the 5 key probe behaviors:
- ✅ Refuses off-topic (salary, legal, competitors, injection)
- ✅ No recommendation on vague turn 1
- ✅ Honors refinements ("add personality tests" updates the list)
- ✅ Comparison uses catalog data only
- ✅ Schema compliance on every response

Recall@10 optimization: hybrid retrieval typically returns higher recall than pure semantic or pure BM25. The 20-candidate pool with LLM reranking to 1–10 maximizes precision while maintaining recall.

## What Didn't Work

- **JS-rendered shl.com catalog**: The main SHL catalog page requires JavaScript; scraped from `online.shl.com` instead
- **Pre-packaged job solutions**: Initially included; filtered to Individual Test Solutions only via `producttypes=1`
- **Pure LLM recommendations**: Without RAG, Gemini hallucinated product names and URLs; retrieval-grounding was essential

## AI Tools Used

Antigravity (Google DeepMind) assisted with code generation. All design decisions, architecture, prompt engineering, and retrieval strategy were reviewed and directed by the developer.

---
*Stack: FastAPI + Gemini 1.5 Flash + all-MiniLM-L6-v2 + FAISS + BM25 | Deployed: Render*
