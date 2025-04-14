# rag_pgvector_store.py
import psycopg2
from psycopg2.extras import Json
from sentence_transformers import SentenceTransformer
import time

# ─── CONFIG ────────────────────────────────────────────
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

VECTOR_DIM = 384  # depends on your model (MiniLM = 384)
model = SentenceTransformer("all-MiniLM-L6-v2")


# ─── DATABASE INIT ─────────────────────────────────────
def init_db(retries=5, delay=3):
    for attempt in range(retries):
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    # Ensure pgvector and pgcrypto extensions are enabled
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
                    conn.commit()

                    # Create logs table with auto-generated UUID and timestamp
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS logs (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            text TEXT NOT NULL,
                            metadata JSONB,
                            embedding vector({VECTOR_DIM}),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)

                    # Create index on agent_id for faster queries
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_agent_id ON logs ((metadata->>'agent_id'));
                    """)

                    # Create index on timestamp for time-based queries
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs ((metadata->>'timestamp'));
                    """)
                    
                    conn.commit()
            print("✅ Database initialized successfully.")
            return
        except psycopg2.OperationalError:
            print(f"🔁 Waiting for PostgreSQL... ({attempt + 1}/{retries})")
            time.sleep(delay)
        except Exception as e:
            print("❌ Failed to initialize database:", e)
            raise

    raise RuntimeError("PostgreSQL not available after multiple attempts.")

# ─── ADD LOG ───────────────────────────────────────────
def add_log(log_text, metadata=None, agent_id=None, log_id=None):
    """
    Add a log entry to the database.
    The database will generate a UUID if none is provided.
    """
    if metadata is None:
        metadata = {}
    if agent_id:
        metadata['agent_id'] = agent_id

    # We'll ignore log_id parameter as the database will generate UUID
    embedding = model.encode([log_text])[0].tolist()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO logs (text, metadata, embedding)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (log_text, Json(metadata), embedding))
            inserted_id = cur.fetchone()[0]
        conn.commit()
    
    return inserted_id


# ─── RETRIEVE SIMILAR LOGS ─────────────────────────────
def retrieve_relevant(query, k=3):
    query_vec = model.encode([query])[0].tolist()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, text, metadata, created_at
                FROM logs
                ORDER BY embedding <-> %s
                LIMIT %s;
            """, (query_vec, k))
            results = cur.fetchall()

    return [
        {
            "id": row[0],
            "text": row[1],
            "metadata": row[2],
            "created_at": row[3],
            "comm_quality": row[2].get("comm_quality"),
            "position": row[2].get("position")
        }
        for row in results
    ]

# ─── GET METADATA ──────────────────────────────────────
def get_metadata(query, k=3):
    query_vec = model.encode([query])[0].tolist()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT metadata
                FROM logs
                ORDER BY embedding <-> %s
                LIMIT %s;
            """, (query_vec, k))
            return [row[0] for row in cur.fetchall()]

# ─── FILTER BY METADATA ────────────────────────────────
def filter_logs_by_jammed(jammed=True):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'jammed' = %s;
            """, (str(jammed).lower(),))
            return [{"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]} for row in cur.fetchall()]

# ─── GET LOGS BY AGENT_ID ──────────────────────────────
def get_logs_by_agent(agent_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'agent_id' = %s
                ORDER BY created_at DESC;
            """, (agent_id,))
            return [{"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]} for row in cur.fetchall()]

# ─── GET LOGS BY TIME PERIOD ───────────────────────────
def get_logs_by_time_period(start_time, end_time, agent_id=None):
    """
    Get logs between start_time and end_time, optionally filtered by agent_id.
    Time format should be ISO: '2023-06-01T00:00:00Z'
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if agent_id:
                cur.execute("""
                    SELECT id, text, metadata, created_at FROM logs
                    WHERE metadata->>'timestamp' >= %s 
                    AND metadata->>'timestamp' <= %s
                    AND metadata->>'agent_id' = %s
                    ORDER BY metadata->>'timestamp' DESC;
                """, (start_time, end_time, agent_id))
            else:
                cur.execute("""
                    SELECT id, text, metadata, created_at FROM logs
                    WHERE metadata->>'timestamp' >= %s 
                    AND metadata->>'timestamp' <= %s
                    ORDER BY metadata->>'timestamp' DESC;
                """, (start_time, end_time))
            
            return [{"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]} for row in cur.fetchall()]

# ─── CLEAR DB ──────────────────────────────────────────
def clear_store():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM logs;")
        conn.commit()

# ─── INIT ON IMPORT ────────────────────────────────────
init_db()