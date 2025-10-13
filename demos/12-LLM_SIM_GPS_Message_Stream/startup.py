#!/usr/bin/env python3
"""
Backend Services Launcher
Starts backend services (NO GUI):
1. Satellite Constellation Server (port 12345)
2. MCP Chatapp (port 5000)

After starting, run the GUI with:
    python main_gui.py
"""

import subprocess
import sys
import time
import signal
from typing import List, Optional

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class ProcessManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.process_names: List[str] = []
        
    def start_process(self, name: str, command: List[str], 
                     wait_time: float = 2.0) -> Optional[subprocess.Popen]:
        """Start a subprocess and track it"""
        print(f"{Colors.OKBLUE}[STARTUP] Starting {name}...{Colors.ENDC}")
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(0.5)
            
            if process.poll() is not None:
                print(f"{Colors.FAIL}[ERROR] {name} failed to start{Colors.ENDC}")
                stdout, stderr = process.communicate()
                if stderr:
                    print(f"{Colors.FAIL}{stderr}{Colors.ENDC}")
                return None
            
            self.processes.append(process)
            self.process_names.append(name)
            
            print(f"{Colors.OKGREEN}[STARTUP] {name} started (PID: {process.pid}){Colors.ENDC}")
            
            if wait_time > 0:
                time.sleep(wait_time)
            
            return process
            
        except Exception as e:
            print(f"{Colors.FAIL}[ERROR] Failed to start {name}: {e}{Colors.ENDC}")
            return None
    
    def stop_all(self):
        """Stop all managed processes"""
        print(f"\n{Colors.WARNING}[SHUTDOWN] Stopping all processes...{Colors.ENDC}")
        
        for process, name in zip(self.processes, self.process_names):
            if process.poll() is None:
                print(f"{Colors.WARNING}[SHUTDOWN] Stopping {name}...{Colors.ENDC}")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"{Colors.FAIL}[SHUTDOWN] Force killing {name}...{Colors.ENDC}")
                    process.kill()
        
        print(f"{Colors.OKGREEN}[SHUTDOWN] All processes stopped{Colors.ENDC}")


def check_dependencies():
    """Check if required packages are installed"""
    print(f"{Colors.HEADER}[CHECK] Checking dependencies...{Colors.ENDC}")
    
    required = ['fastapi', 'uvicorn', 'psycopg2', 'pynmea2', 'httpx']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"{Colors.FAIL}[ERROR] Missing packages: {', '.join(missing)}{Colors.ENDC}")
        return False
    
    print(f"{Colors.OKGREEN}[CHECK] All dependencies found{Colors.ENDC}")
    return True


def check_database():
    """Check if PostgreSQL is running"""
    print(f"{Colors.HEADER}[CHECK] Checking database...{Colors.ENDC}")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname="rag_db",
            user="postgres",
            password="password",
            host="localhost",
            port="5432"
        )
        conn.close()
        print(f"{Colors.OKGREEN}[CHECK] Database connection OK{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] Database not available: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}Start with: docker compose up -d{Colors.ENDC}")
        return False


def main():
    banner = """
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║         GPS SIMULATION BACKEND SERVICES               ║
║                                                       ║
║  Components:                                          ║
║    • Satellite Constellation (port 12345)             ║
║    • MCP Chatapp (port 5000)                          ║
║                                                       ║
║  After starting, launch GUI with:                     ║
║    python main_gui.py                                 ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
"""
    print(f"{Colors.HEADER}{banner}{Colors.ENDC}")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    if not check_database():
        sys.exit(1)
    
    manager = ProcessManager()
    
    def signal_handler(sig, frame):
        print(f"\n{Colors.WARNING}[SIGNAL] Received interrupt{Colors.ENDC}")
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start Satellite Constellation
        process = manager.start_process(
            "Satellite Constellation",
            [sys.executable, "sat_constellation.py"],
            wait_time=3.0
        )
        if not process:
            print(f"{Colors.WARNING}[WARNING] Continuing without GPS{Colors.ENDC}")
        
        # Start MCP Chatapp
        process = manager.start_process(
            "MCP Chatapp",
            [sys.executable, "mcp_chatapp.py"],
            wait_time=3.0
        )
        if not process:
            print(f"{Colors.WARNING}[WARNING] MCP chatapp failed{Colors.ENDC}")
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}[READY] Backend services running!{Colors.ENDC}")
        print(f"\n{Colors.OKGREEN}Access points:{Colors.ENDC}")
        print(f"  • MCP Chatapp:     http://localhost:5000")
        print(f"  • Constellation:   tcp://localhost:12345")
        
        print(f"\n{Colors.OKGREEN}[INFO] Now run: python main_gui.py{Colors.ENDC}")
        print(f"{Colors.WARNING}[INFO] Press Ctrl+C to shutdown{Colors.ENDC}\n")
        
        # Keep running
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] {e}{Colors.ENDC}")
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()