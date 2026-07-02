"""
Hybrid BM25 + FAISS Retrieval Engine for SHL Assessment Catalog
"""
import json
import numpy as np
import faiss
import os
import re
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi


# ─────────────────────────────────────────────
# Catalog Loading
# ─────────────────────────────────────────────

CATALOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'catalog.json')

_catalog: List[Dict] = []
_bm25: BM25Okapi = None
_faiss_index: faiss.IndexFlatIP = None
_embedder = None
_doc_vectors: np.ndarray = None


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for BM25"""
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _get_doc_text(product: Dict) -> str:
    """Build a rich text representation of a product for indexing"""
    parts = [
        product.get('name', ''),
        product.get('description', ''),
        ' '.join(product.get('product_types', [])),
        ' '.join(product.get('keywords', [])),
    ]
    return ' '.join(p for p in parts if p)


def load_catalog() -> List[Dict]:
    """Load catalog from JSON file"""
    global _catalog
    if _catalog:
        return _catalog
    
    catalog_path = os.path.abspath(CATALOG_PATH)
    with open(catalog_path, 'r', encoding='utf-8') as f:
        _catalog = json.load(f)
    
    return _catalog


def build_index():
    """Build BM25 and FAISS indices for retrieval"""
    global _bm25, _faiss_index, _embedder, _doc_vectors, _catalog
    
    catalog = load_catalog()
    
    # Build BM25 index
    doc_texts = [_get_doc_text(p) for p in catalog]
    tokenized = [_tokenize(text) for text in doc_texts]
    _bm25 = BM25Okapi(tokenized)
    
    # Build FAISS index with sentence transformers
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("Building embedding index...")
        _doc_vectors = _embedder.encode(doc_texts, show_progress_bar=False)
        _doc_vectors = _doc_vectors.astype(np.float32)
        
        # Normalize for cosine similarity
        norms = np.linalg.norm(_doc_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        _doc_vectors /= norms
        
        # Build FAISS inner product index (cosine similarity after normalization)
        dim = _doc_vectors.shape[1]
        _faiss_index = faiss.IndexFlatIP(dim)
        _faiss_index.add(_doc_vectors)
        print(f"Indexed {len(catalog)} products in FAISS")
    except Exception as e:
        print(f"Warning: Could not build FAISS index: {e}")
        _faiss_index = None
    
    return catalog


def hybrid_search(query: str, k: int = 20) -> List[Tuple[int, float]]:
    """
    Hybrid BM25 + Dense retrieval
    Returns list of (index, score) tuples sorted by combined score
    """
    catalog = load_catalog()
    n = len(catalog)
    
    # BM25 scores
    tokens = _tokenize(query)
    bm25_scores = np.array(_bm25.get_scores(tokens))
    bm25_max = bm25_scores.max() if bm25_scores.max() > 0 else 1
    bm25_norm = bm25_scores / bm25_max
    
    # Dense scores
    if _faiss_index is not None and _embedder is not None:
        query_vec = _embedder.encode([query]).astype(np.float32)
        qnorm = np.linalg.norm(query_vec)
        if qnorm > 0:
            query_vec /= qnorm
        
        k_faiss = min(n, k * 2)
        dense_scores_raw, indices = _faiss_index.search(query_vec, k_faiss)
        
        dense_scores = np.zeros(n)
        for idx, score in zip(indices[0], dense_scores_raw[0]):
            if 0 <= idx < n:
                dense_scores[idx] = max(0, score)
        dense_max = dense_scores.max() if dense_scores.max() > 0 else 1
        dense_norm = dense_scores / dense_max
        
        # Hybrid: 40% BM25 + 60% dense
        combined = 0.4 * bm25_norm + 0.6 * dense_norm
    else:
        combined = bm25_norm
    
    # Get top-k
    top_k_indices = np.argsort(combined)[::-1][:k]
    results = [(int(idx), float(combined[idx])) for idx in top_k_indices if combined[idx] > 0]
    
    return results


def search_assessments(query: str, k: int = 15, 
                        type_filter: str = None) -> List[Dict]:
    """
    Search the assessment catalog and return top matches
    
    Args:
        query: Search query
        k: Number of results to return
        type_filter: Optional filter by test_type code (e.g., 'K', 'P', 'A')
    
    Returns:
        List of matching assessment dicts
    """
    catalog = load_catalog()
    results = hybrid_search(query, k=50)
    
    # Filter and rank
    matches = []
    for idx, score in results:
        product = catalog[idx]
        
        # Apply type filter if specified
        if type_filter and product.get('test_type') != type_filter:
            continue
        
        matches.append({**product, '_score': score})
    
    return matches[:k]


def get_assessment_by_name(name: str) -> Dict:
    """Exact or fuzzy name lookup"""
    catalog = load_catalog()
    name_lower = name.lower()
    
    # Exact match
    for product in catalog:
        if product['name'].lower() == name_lower:
            return product
    
    # Fuzzy match
    for product in catalog:
        if name_lower in product['name'].lower() or product['name'].lower() in name_lower:
            return product
    
    return None


def get_catalog_summary() -> str:
    """Return a compact catalog summary for the system prompt"""
    catalog = load_catalog()
    lines = []
    for p in catalog:
        types = ', '.join(p.get('product_types', [p.get('test_type', 'A')]))
        desc = p.get('description', '')[:120]
        lines.append(f"- {p['name']} [{p['test_type']}] ({types}): {desc}")
    return '\n'.join(lines)


def get_assessments_for_comparison(names: List[str]) -> List[Dict]:
    """Get full data for named assessments for comparison"""
    results = []
    for name in names:
        product = get_assessment_by_name(name)
        if product:
            results.append(product)
    return results
