#!/usr/bin/env python3
# clear_database.py
"""
Simple script to clear all logs from the RAG vector database.
"""

import psycopg2

# Database configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

def clear_database():
    """Clear all logs from the database."""
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM logs;")
            conn.commit()
        print("✅ Database cleared successfully.")
    except Exception as e:
        print(f"❌ Error clearing database: {e}")

if __name__ == "__main__":
    confirmation = input("Are you sure you want to clear all logs? (yes/no): ")
    if confirmation.lower() == "yes":
        clear_database()
    else:
        print("Operation cancelled.")