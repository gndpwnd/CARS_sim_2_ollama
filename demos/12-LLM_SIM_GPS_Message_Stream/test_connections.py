#!/usr/bin/env python3
"""Test all connections"""
import requests
import socket

def test_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✓ Ollama connection OK")
            return True
    except:
        print("✗ Ollama connection failed")
        return False

def test_postgres():
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname="rag_db", user="postgres", 
            password="password", host="localhost", port="5432"
        )
        conn.close()
        print("✓ PostgreSQL connection OK")
        return True
    except:
        print("✗ PostgreSQL connection failed")
        return False

def test_gps_constellation():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 12345))
        sock.close()
        if result == 0:
            print("✓ GPS Constellation connection OK")
            return True
        else:
            print("✗ GPS Constellation not running")
            return False
    except:
        print("✗ GPS Constellation connection failed")
        return False

if __name__ == "__main__":
    print("Testing connections...")
    test_ollama()
    test_postgres() 
    test_gps_constellation()