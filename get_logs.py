
# fetch_all_logs.py
"""
Simple script to fetch all logs from the RAG vector database.
"""

import psycopg2
import json
from datetime import datetime
import argparse

# Database configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

def check_schema():
    """Check if the created_at column exists, if not, add it."""
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Check if created_at column exists
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'logs' AND column_name = 'created_at';
                """)
                if not cur.fetchone():
                    print("Adding created_at column to logs table...")
                    cur.execute("""
                        ALTER TABLE logs 
                        ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    """)
                    conn.commit()
                    print("Column added successfully.")
    except Exception as e:
        print(f"Error checking/updating schema: {e}")

def fetch_all_logs(limit=None, output_file=None, format_json=False):
    """
    Fetch all logs from the database.
    
    Parameters:
    - limit: Optional maximum number of logs to retrieve
    - output_file: Optional file path to save results
    - format_json: Whether to format JSON with indentation
    """
    try:
        # First check if schema needs updating
        check_schema()
        
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Query database structure to get available columns
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'logs';
                """)
                columns = [row[0] for row in cur.fetchall()]
                
                # Build dynamic query based on available columns
                select_cols = ["id", "text", "metadata"]
                if "created_at" in columns:
                    select_cols.append("created_at")
                
                query = f"""
                    SELECT {', '.join(select_cols)} FROM logs
                    ORDER BY {"created_at" if "created_at" in columns else "id"} DESC
                """
                
                if limit:
                    query += " LIMIT %s"
                    cur.execute(query, (limit,))
                else:
                    cur.execute(query)
                
                results = []
                for row in cur.fetchall():
                    result = {
                        "id": str(row[0]),  # Convert UUID to string
                        "text": row[1],
                        "metadata": row[2],
                    }
                    
                    # Add created_at if it exists
                    if "created_at" in columns and len(row) > 3:
                        result["created_at"] = row[3].isoformat() if row[3] else None
                    
                    results.append(result)
                
                print(f"✅ Retrieved {len(results)} logs")
                
                if output_file:
                    indent = 2 if format_json else None
                    with open(output_file, 'w') as f:
                        json.dump(results, f, indent=indent)
                    print(f"✅ Logs saved to {output_file}")
                else:
                    # Print to console
                    if format_json:
                        print(json.dumps(results, indent=2))
                    else:
                        for i, log in enumerate(results, 1):
                            print(f"\n--- Log {i} ---")
                            print(f"ID: {log['id']}")
                            if "created_at" in log:
                                print(f"Created: {log['created_at']}")
                            print(f"Text: {log['text']}")
                            print(f"Metadata: {json.dumps(log['metadata'], indent=2)}")
                
                return results
                
    except Exception as e:
        print(f"❌ Error fetching logs: {e}")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch logs from the RAG database")
    parser.add_argument("-l", "--limit", type=int, help="Limit the number of logs returned")
    parser.add_argument("-o", "--output", help="Output file path for JSON results")
    parser.add_argument("-f", "--format", action="store_true", help="Format JSON with indentation")
    parser.add_argument("--update-schema", action="store_true", 
                        help="Update database schema to add created_at column if missing")
    
    args = parser.parse_args()
    
    if args.update_schema:
        check_schema()
    
    fetch_all_logs(limit=args.limit, output_file=args.output, format_json=args.format)