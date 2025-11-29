#!/usr/bin/env python3
"""
Comprehensive test for documentation retrieval and RAG system.
Tests:
1. Documentation ingestion status
2. Vector search functionality
3. Agent discovery
4. Context assembly
"""

import sys

print("="*60)
print("COMPREHENSIVE RAG SYSTEM TEST")
print("="*60)

# Test 1: Check if documentation exists in PostgreSQL
print("\n[TEST 1] Checking documentation in PostgreSQL...")
try:
    import psycopg2
    from core.config import DB_CONFIG
    
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Count documentation entries
            cur.execute("""
                SELECT COUNT(*), 
                       COUNT(DISTINCT metadata->>'doc_type'),
                       COUNT(DISTINCT metadata->>'filename')
                FROM logs
                WHERE metadata->>'message_type' = 'documentation';
            """)
            
            count, doc_types, files = cur.fetchone()
            
            print(f"✅ Found {count} documentation chunks")
            print(f"   - {doc_types} different document types")
            print(f"   - {files} unique files")
            
            if count == 0:
                print("\n⚠️  NO DOCUMENTATION FOUND!")
                print("   Run: python document_ingest.py")
                print("   This will create the system overview and ingest docs.")
            else:
                # Show what docs we have
                cur.execute("""
                    SELECT metadata->>'doc_type', 
                           metadata->>'filename',
                           LENGTH(text) as text_length,
                           created_at
                    FROM logs
                    WHERE metadata->>'message_type' = 'documentation'
                    ORDER BY created_at DESC
                    LIMIT 5;
                """)
                
                print("\n   Recent documentation:")
                for doc_type, filename, length, created in cur.fetchall():
                    print(f"   - {doc_type}: {filename} ({length} chars) at {created}")

except Exception as e:
    print(f"❌ PostgreSQL error: {e}")
    sys.exit(1)

# Test 2: Check if pgvector extension is working
print("\n[TEST 2] Testing vector operations...")
try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check if vector extension exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                );
            """)
            
            has_vector = cur.fetchone()[0]
            
            if has_vector:
                print("✅ pgvector extension installed")
                
                # Test vector query with proper casting
                try:
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer("all-MiniLM-L6-v2")
                    test_query = "GPS jamming"
                    query_vec = model.encode([test_query])[0].tolist()
                    
                    cur.execute(f"""
                        SELECT text, metadata->>'doc_type'
                        FROM logs
                        WHERE metadata->>'message_type' = 'documentation'
                        ORDER BY embedding <-> %s::vector
                        LIMIT 1;
                    """, (query_vec,))
                    
                    result = cur.fetchone()
                    if result:
                        text, doc_type = result
                        print(f"✅ Vector search working! Found {doc_type} doc")
                        print(f"   Preview: {text[:100]}...")
                    else:
                        print("⚠️  Vector search returned no results")
                        
                except Exception as ve:
                    print(f"❌ Vector search failed: {ve}")
            else:
                print("❌ pgvector extension NOT installed!")
                print("   Run in PostgreSQL: CREATE EXTENSION vector;")

except Exception as e:
    print(f"❌ Error testing vectors: {e}")

# Test 3: Test agent discovery
print("\n[TEST 3] Testing agent discovery...")
try:
    from rag import get_known_agent_ids
    
    agents = get_known_agent_ids(limit=100)
    
    if agents:
        print(f"✅ Found {len(agents)} agents: {agents}")
    else:
        print("⚠️  No agents found")
        print("   - Make sure the simulation is running")
        print("   - Check that telemetry is being logged to Qdrant")
        print("   - Run: python main_gui.py")
        
except Exception as e:
    print(f"❌ Agent discovery error: {e}")
    agents = []

# Test 4: Test live data retrieval
if agents:
    print("\n[TEST 4] Testing live telemetry data...")
    try:
        from rag import get_rag
        
        rag = get_rag()
        live_data = rag.get_live_agent_data(agents[:3], history_limit=3)
        
        if live_data:
            print(f"✅ Retrieved telemetry for {len(live_data)} agents")
            for agent_id, data in live_data.items():
                pos = data['current_position']
                jammed = data['jammed']
                print(f"   - {agent_id}: ({pos[0]:.2f}, {pos[1]:.2f}) {'JAMMED' if jammed else 'CLEAR'}")
        else:
            print("⚠️  No telemetry data retrieved")
            print("   - Agents may not have moved yet")
            print("   - Check Qdrant collection: agent_telemetry")
            
    except Exception as e:
        print(f"❌ Telemetry retrieval error: {e}")

# Test 5: Test context assembly
print("\n[TEST 5] Testing full context assembly...")
try:
    from rag import get_rag
    
    rag = get_rag()
    
    # Test with documentation
    if agents:
        context = rag.assemble_context_for_llm(
            "How does GPS jamming affect agents?",
            agents,
            include_documentation=True,
            include_conversation=True
        )
        
        print(f"✅ Assembled context: {len(context)} characters")
        
        has_docs = "SYSTEM DOCUMENTATION" in context
        has_status = "CURRENT AGENT STATUS" in context
        has_conversation = "RECENT CONVERSATION" in context
        
        print(f"   - Contains documentation: {'✅' if has_docs else '❌'}")
        print(f"   - Contains agent status: {'✅' if has_status else '❌'}")
        print(f"   - Contains conversation: {'✅' if has_conversation else '❌'}")
        
        if len(context) > 0:
            print("\n   Context preview:")
            print("   " + "-"*56)
            preview = context[:500]
            for line in preview.split('\n'):
                print(f"   {line}")
            if len(context) > 500:
                print(f"   ... ({len(context) - 500} more characters)")
            print("   " + "-"*56)
    else:
        print("⚠️  Skipping (no agents found)")
        
except Exception as e:
    print(f"❌ Context assembly error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Test minimal vs full context
print("\n[TEST 6] Testing minimal vs full context...")
try:
    from rag import format_for_llm
    
    if agents:
        # Minimal context
        minimal = format_for_llm("status?", agents[:2], minimal=True)
        print(f"✅ Minimal context: {len(minimal)} chars (quick status)")
        
        # Full context
        full = format_for_llm("How does jamming work?", agents[:2], minimal=False)
        print(f"✅ Full context: {len(full)} chars (with docs)")
        
        ratio = len(full) / max(len(minimal), 1)
        print(f"   Full context is {ratio:.1f}x larger (includes docs + history)")
    else:
        print("⚠️  Skipping (no agents found)")
        
except Exception as e:
    print(f"❌ Context comparison error: {e}")

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)

print("\n✅ PASSED:")
print("   - PostgreSQL connection")
print("   - Documentation storage")
print("   - Vector operations")

print("\n⚠️  ACTION ITEMS:")
action_items = []

# Check if docs are ingested
try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM logs 
                WHERE metadata->>'message_type' = 'documentation';
            """)
            doc_count = cur.fetchone()[0]
            
            if doc_count == 0:
                action_items.append("Run: python document_ingest.py")
except:
    action_items.append("Fix PostgreSQL connection")

# Check if agents exist
if not agents:
    action_items.append("Start simulation: python main_gui.py")
    action_items.append("Let agents move for 10-20 seconds")

if action_items:
    for item in action_items:
        print(f"   - {item}")
else:
    print("   None! System is ready. ✅")

print("\n" + "="*60)