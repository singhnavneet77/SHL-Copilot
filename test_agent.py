"""
Test script to verify the agent works correctly
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Message
from app.retriever import build_index, load_catalog

async def test_agent():
    print("=" * 60)
    print("SHL Assessment Agent - Test Suite")
    print("=" * 60)
    
    # Build index first
    print("\n1. Building retrieval index...")
    build_index()
    catalog = load_catalog()
    print(f"   Loaded {len(catalog)} products")
    
    # Test retrieval
    print("\n2. Testing retrieval...")
    from app.retriever import search_assessments
    
    tests = [
        ("Java developer", 5),
        ("Python programming", 5),
        ("personality assessment", 5),
        ("verbal reasoning", 5),
        ("customer service call center", 5),
    ]
    
    for query, k in tests:
        results = search_assessments(query, k=k)
        print(f"   Query '{query}': {len(results)} results")
        for r in results[:2]:
            print(f"     - {r['name'][:40]} [{r['test_type']}]")
    
    # Test agent
    print("\n3. Testing agent...")
    from app.agent import process_chat
    
    # Test 1: Vague query (should clarify)
    messages = [Message(role="user", content="I need an assessment")]
    response = await process_chat(messages)
    print(f"\n   Test 1 (Vague query):")
    print(f"   Reply: {response.reply[:100]}")
    print(f"   Recommendations: {len(response.recommendations)}")
    assert len(response.recommendations) == 0, "Should NOT recommend on vague query!"
    print("   PASS: No recommendations on vague query")
    
    # Test 2: Specific Java developer query
    messages = [
        Message(role="user", content="I'm hiring a Java developer with 4 years experience who will work with stakeholders"),
        Message(role="assistant", content="What is their seniority level?"),
        Message(role="user", content="Mid-level, around 4 years"),
    ]
    response = await process_chat(messages)
    print(f"\n   Test 2 (Java developer):")
    print(f"   Reply: {response.reply[:100]}")
    print(f"   Recommendations: {len(response.recommendations)}")
    if response.recommendations:
        for rec in response.recommendations[:3]:
            print(f"     - {rec.name} [{rec.test_type}] -> {rec.url[:50]}")
    
    # Test 3: Off-topic (salary question)
    messages = [Message(role="user", content="What salary should I offer this candidate?")]
    response = await process_chat(messages)
    print(f"\n   Test 3 (Off-topic salary):")
    print(f"   Reply: {response.reply[:100]}")
    print(f"   Recommendations: {len(response.recommendations)}")
    assert len(response.recommendations) == 0, "Should NOT recommend for off-topic!"
    print("   PASS: Properly refused off-topic query")
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_agent())
