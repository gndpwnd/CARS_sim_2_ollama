#!/usr/bin/env python3
"""
Fix PostgreSQL vector type issues.
This script ensures embeddings are stored correctly and queries work.
"""

import psycopg2
from sentence_transformers import SentenceTransformer

print("="*60)
print("FIXING POSTGRESQL VECTOR TYPES")
print("="*60)

# Configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

VECTOR_DIM = 384

# Step 1: Verify vector extension
print("\n[1/4] Checking vector extension...")
try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check extension
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                );
            """)
            has_vector = cur.fetchone()[0]
            
            if has_vector:
                print("✅ Vector extension installed")
            else:
                print("❌ Vector extension missing!")
                print("   Installing...")
                conn.autocommit = True
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                print("✅ Vector extension installed")
                
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Step 2: Check table structure
print("\n[2/4] Checking table structure...")
try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Check if embedding column exists and its type
            cur.execute("""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'logs' AND column_name = 'embedding';
            """)
            
            result = cur.fetchone()
            if result:
                col_name, data_type, udt_name = result
                print(f"✅ Embedding column exists")
                print(f"   Type: {data_type} ({udt_name})")
                
                if udt_name != 'vector':
                    print("⚠️  Column type is not 'vector'")
                    print("   This might cause issues with vector operations")
            else:
                print("❌ Embedding column missing!")
                
except Exception as e:
    print(f"❌ Error: {e}")

# Step 3: Test vector query
print("\n[3/4] Testing vector query...")
try:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    test_query = "test query"
    query_vec = model.encode([test_query])[0].tolist()
    
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Try the query with proper casting
            cur.execute(f"""
                SELECT id, text
                FROM logs
                WHERE embedding IS NOT NULL
                ORDER BY embedding <-> %s::vector
                LIMIT 1;
            """, (query_vec,))
            
            result = cur.fetchone()
            if result:
                print("✅ Vector query successful!")
                log_id, text = result
                print(f"   Found log: {text[:50]}...")
            else:
                print("⚠️  No results (table might be empty)")
                
except Exception as e:
    print(f"❌ Vector query failed: {e}")
    print("\n   This usually means:")
    print("   1. Embeddings weren't stored as vector type")
    print("   2. The embedding column needs to be recreated")
    
    print("\n   To fix, we can recreate the embedding column...")
    
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                print("   Dropping old embedding column...")
                cur.execute("ALTER TABLE logs DROP COLUMN IF EXISTS embedding;")
                
                print(f"   Creating new embedding column (vector({VECTOR_DIM}))...")
                cur.execute(f"""
                    ALTER TABLE logs 
                    ADD COLUMN embedding vector({VECTOR_DIM});
                """)
                
                conn.commit()
                print("✅ Embedding column recreated!")
                print("   ⚠️  You'll need to re-ingest documentation:")
                print("   Run: python document_ingest.py")
                
    except Exception as fix_error:
        print(f"❌ Could not fix: {fix_error}")

# Step 4: Count existing data
print("\n[4/4] Checking data...")
try:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # Count total logs
            cur.execute("SELECT COUNT(*) FROM logs;")
            total = cur.fetchone()[0]
            
            # Count docs
            cur.execute("""
                SELECT COUNT(*) FROM logs 
                WHERE metadata->>'message_type' = 'documentation';
            """)
            docs = cur.fetchone()[0]
            
            # Count logs with embeddings
            cur.execute("SELECT COUNT(*) FROM logs WHERE embedding IS NOT NULL;")
            with_embeddings = cur.fetchone()[0]
            
            print(f"   Total logs: {total}")
            print(f"   Documentation: {docs}")
            print(f"   With embeddings: {with_embeddings}")
            
            if docs > 0 and with_embeddings == 0:
                print("\n⚠️  Documentation exists but has no embeddings!")
                print("   This means docs were added without embeddings")
                print("   Re-run: python document_ingest.py")
                
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)
print("FIX COMPLETE")
print("="*60)
print("\nNext steps:")
print("1. If embeddings were recreated, run: python document_ingest.py")
print("2. Start simulation: python main_gui.py")
print("3. Test RAG: python test_documentation_retrieval.py")
print("="*60)