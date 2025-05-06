# rag_store.py

import psycopg2
from psycopg2.extras import Json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from uuid import uuid4
import time

# ─── CONFIG ────────────────────────────────────────────
VECTOR_DIM = 384
EMBED_MODEL = "all-MiniLM-L6-v2"
QDRANT_COLLECTION = "logs"

DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

qdrant_client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer(EMBED_MODEL)

# ─── INIT QDRANT + POSTGRES ───────────────────────────
def init_stores():
    # Init PostgreSQL tables and extensions
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id UUID PRIMARY KEY,
                        text TEXT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
        print("✅ PostgreSQL ready.")
    except Exception as e:
        print("❌ PostgreSQL init failed:", e)
        raise

    # Init Qdrant collection
    if not qdrant_client.collection_exists(QDRANT_COLLECTION):
        qdrant_client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
        )
        print("✅ Qdrant collection created.")

# ─── ADD LOG ───────────────────────────────────────────
def add_log(log_text, metadata=None, agent_id=None):
    if metadata is None:
        metadata = {}
    if agent_id:
        metadata["agent_id"] = agent_id

    log_id = str(uuid4())
    vector = model.encode(log_text).tolist()

    # Insert into PostgreSQL
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO logs (id, text, metadata)
                VALUES (%s, %s, %s);
            """, (log_id, log_text, Json(metadata)))
        conn.commit()

    # Insert into Qdrant
    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[PointStruct(id=log_id, vector=vector, payload=metadata)]
    )

    return log_id

# ─── RETRIEVE SIMILAR LOGS ─────────────────────────────
def retrieve_relevant(query, k=3):
    vector = model.encode(query).tolist()
    results = qdrant_client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=k
    )
    ids = [r.id for r in results]

    if not ids:
        return []

    # Fetch matching metadata/text from PostgreSQL
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, metadata, created_at FROM logs WHERE id = ANY(%s);",
                (ids,)
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "text": r[1],
            "metadata": r[2],
            "created_at": r[3],
            "comm_quality": r[2].get("comm_quality"),
            "position": r[2].get("position")
        }
        for r in rows
    ]

# ─── FILTER BY METADATA ────────────────────────────────
def filter_logs_by_jammed(jammed=True):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'jammed' = %s;
            """, (str(jammed).lower(),))
            return [
                {"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]}
                for row in cur.fetchall()
            ]

# ─── GET LOGS BY AGENT_ID ──────────────────────────────
def get_logs_by_agent(agent_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata, created_at FROM logs
                WHERE metadata->>'agent_id' = %s
                ORDER BY created_at DESC;
            """, (agent_id,))
            return [
                {"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]}
                for row in cur.fetchall()
            ]

# ─── GET LOGS BY TIME PERIOD ───────────────────────────
def get_logs_by_time_period(start_time, end_time, agent_id=None):
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
            return [
                {"id": row[0], "text": row[1], "metadata": row[2], "created_at": row[3]}
                for row in cur.fetchall()
            ]
