# posgresql_store.py - PostgreSQL for User/LLM/Agent Messages
import psycopg2
from psycopg2.extras import Json
from sentence_transformers import SentenceTransformer
import time
from datetime import datetime

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
            # Create extensions separately
            try:
                with psycopg2.connect(**DB_CONFIG) as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            except psycopg2.errors.UniqueViolation as e:
                print(f"Extension already exists, continuing: {e}")
                pass
            
            # Create tables in a separate transaction
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    # Create logs table with message structure
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS logs (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            text TEXT NOT NULL,
                            metadata JSONB,
                            embedding vector({VECTOR_DIM}),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)

                    # Create indexes for efficient querying
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_source 
                        ON logs ((metadata->>'source'));
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_message_type 
                        ON logs ((metadata->>'message_type'));
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                        ON logs ((metadata->>'timestamp'));
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


# ─── ADD LOG WITH MESSAGE STRUCTURE ────────────────────
def add_log(log_text, metadata=None, agent_id=None, log_id=None):
    """
    Add a message log to PostgreSQL
    
    Args:
        log_text: Message content
        metadata: Dictionary with:
            - source: "user" | "llm" | "agent_1" | "agent_2" | ...
            - message_type: "command" | "response" | "notification" | "error" | "telemetry"
            - timestamp: ISO format timestamp
            - other relevant fields
        agent_id: Legacy parameter (adds to metadata if provided)
        log_id: Ignored (UUID auto-generated)
    
    Returns:
        Inserted UUID
    """
    if metadata is None:
        metadata = {}
    
    # Add agent_id to metadata if provided separately
    if agent_id and 'agent_id' not in metadata:
        metadata['agent_id'] = agent_id
    
    # Ensure required fields exist
    if 'source' not in metadata:
        metadata['source'] = 'system'
    
    if 'message_type' not in metadata:
        metadata['message_type'] = 'notification'
    
    if 'timestamp' not in metadata:
        metadata['timestamp'] = datetime.now().isoformat()
    
    # Generate embedding
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
            "source": row[2].get("source"),
            "message_type": row[2].get("message_type")
        }
        for row in results
    ]


# ─── GET MESSAGES BY SOURCE ────────────────────────────
def get_messages_by_source(source, limit=50):
    """
    Get messages from a specific source
    
    Args:
        source: "user" | "llm" | "agent_1" | etc.
        limit: Max number of messages
    
    Returns:
        List of message records
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at 
                FROM logs
                WHERE metadata->>'source' = %s
                ORDER BY created_at DESC
                LIMIT %s;
            """, (source, limit))
            return [
                {
                    "id": row[0],
                    "text": row[1],
                    "metadata": row[2],
                    "created_at": row[3]
                }
                for row in cur.fetchall()
            ]


# ─── GET MESSAGES BY TYPE ──────────────────────────────
def get_messages_by_type(message_type, limit=50):
    """
    Get messages by type
    
    Args:
        message_type: "command" | "response" | "notification" | "error" | "telemetry"
        limit: Max number of messages
    
    Returns:
        List of message records
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at 
                FROM logs
                WHERE metadata->>'message_type' = %s
                ORDER BY created_at DESC
                LIMIT %s;
            """, (message_type, limit))
            return [
                {
                    "id": row[0],
                    "text": row[1],
                    "metadata": row[2],
                    "created_at": row[3]
                }
                for row in cur.fetchall()
            ]


# ─── GET AGENT ERRORS ──────────────────────────────────
def get_agent_errors(agent_id=None, limit=50):
    """
    Get error messages, optionally filtered by agent
    
    Args:
        agent_id: Optional agent filter (e.g., "agent_1")
        limit: Max number of errors
    
    Returns:
        List of error records
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if agent_id:
                cur.execute("""
                    SELECT id, text, metadata, created_at 
                    FROM logs
                    WHERE metadata->>'message_type' = 'error'
                    AND metadata->>'source' = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (agent_id, limit))
            else:
                cur.execute("""
                    SELECT id, text, metadata, created_at 
                    FROM logs
                    WHERE metadata->>'message_type' = 'error'
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (limit,))
            
            return [
                {
                    "id": row[0],
                    "text": row[1],
                    "metadata": row[2],
                    "created_at": row[3]
                }
                for row in cur.fetchall()
            ]


# ─── GET CONVERSATION HISTORY ──────────────────────────
def get_conversation_history(limit=100):
    """
    Get user/LLM conversation history (excludes system messages)
    
    Args:
        limit: Max number of messages
    
    Returns:
        List of conversation messages
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at 
                FROM logs
                WHERE metadata->>'source' IN ('user', 'llm')
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            return [
                {
                    "id": row[0],
                    "text": row[1],
                    "metadata": row[2],
                    "created_at": row[3],
                    "role": row[2].get("source")
                }
                for row in cur.fetchall()
            ]


# ─── LEGACY FUNCTIONS (MAINTAINED FOR COMPATIBILITY) ───
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


def filter_logs_by_jammed(jammed=True):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'jammed' = %s;
            """, (str(jammed).lower(),))
            return [{"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]} for row in cur.fetchall()]


def get_logs_by_agent(agent_id):
    """Get all logs for a specific agent"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'source' = %s
                ORDER BY created_at DESC;
            """, (agent_id,))
            return [{"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]} for row in cur.fetchall()]


def get_logs_by_time_period(start_time, end_time, agent_id=None):
    """Get logs between start_time and end_time"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if agent_id:
                cur.execute("""
                    SELECT id, text, metadata, created_at FROM logs
                    WHERE metadata->>'timestamp' >= %s 
                    AND metadata->>'timestamp' <= %s
                    AND metadata->>'source' = %s
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


def clear_store():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM logs;")
        conn.commit()


# ─── INIT ON IMPORT ────────────────────────────────────
init_db()