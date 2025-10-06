#!/usr/bin/env python3
"""
Integrated GPS Simulation Startup Script

Starts all components in the correct order:
1. Satellite Constellation Server
2. Requirements Monitor  
3. Agent Simulation with GPS Client
4. MCP Chatapp with RAG

Usage:
    python startup.py [--no-gps] [--no-requirements] [--no-simulation] [--no-mcp]
"""

import subprocess
import sys
import time
import signal
import argparse
import os
from typing import List, Optional

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ProcessManager:
    """Manages subprocess lifecycle for the integrated system"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.process_names: List[str] = []
        
    def start_process(self, name: str, command: List[str], 
                     wait_time: float = 2.0) -> Optional[subprocess.Popen]:
        """
        Start a subprocess and track it
        
        Args:
            name: Process name for logging
            command: Command and arguments to execute
            wait_time: Time to wait after starting
            
        Returns:
            Subprocess object or None if failed
        """
        print(f"{Colors.OKBLUE}[STARTUP] Starting {name}...{Colors.ENDC}")
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a bit to see if it crashes immediately
            time.sleep(0.5)
            
            if process.poll() is not None:
                # Process terminated immediately
                print(f"{Colors.FAIL}[ERROR] {name} failed to start{Colors.ENDC}")
                stdout, stderr = process.communicate()
                if stderr:
                    print(f"{Colors.FAIL}{stderr}{Colors.ENDC}")
                return None
            
            self.processes.append(process)
            self.process_names.append(name)
            
            print(f"{Colors.OKGREEN}[STARTUP] {name} started (PID: {process.pid}){Colors.ENDC}")
            
            if wait_time > 0:
                print(f"{Colors.OKCYAN}[STARTUP] Waiting {wait_time}s for {name} to initialize...{Colors.ENDC}")
                time.sleep(wait_time)
            
            return process
            
        except FileNotFoundError:
            print(f"{Colors.FAIL}[ERROR] Command not found: {' '.join(command)}{Colors.ENDC}")
            return None
        except Exception as e:
            print(f"{Colors.FAIL}[ERROR] Failed to start {name}: {e}{Colors.ENDC}")
            return None
    
    def stop_all(self):
        """Stop all managed processes"""
        print(f"\n{Colors.WARNING}[SHUTDOWN] Stopping all processes...{Colors.ENDC}")
        
        for process, name in zip(self.processes, self.process_names):
            if process.poll() is None:  # Still running
                print(f"{Colors.WARNING}[SHUTDOWN] Stopping {name} (PID: {process.pid})...{Colors.ENDC}")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"{Colors.FAIL}[SHUTDOWN] Force killing {name}...{Colors.ENDC}")
                    process.kill()
                except Exception as e:
                    print(f"{Colors.FAIL}[SHUTDOWN] Error stopping {name}: {e}{Colors.ENDC}")
        
        print(f"{Colors.OKGREEN}[SHUTDOWN] All processes stopped{Colors.ENDC}")
    
    def check_health(self):
        """Check if all processes are still running"""
        all_healthy = True
        
        for process, name in zip(self.processes, self.process_names):
            if process.poll() is not None:
                print(f"{Colors.FAIL}[HEALTH] {name} has stopped unexpectedly{Colors.ENDC}")
                all_healthy = False
        
        return all_healthy


def check_dependencies():
    """Check if required Python packages are installed"""
    print(f"{Colors.HEADER}[STARTUP] Checking dependencies...{Colors.ENDC}")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'psycopg2',
        'ollama',
        'matplotlib',
        'numpy',
        'pynmea2',
        'httpx'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"{Colors.FAIL}[ERROR] Missing required packages:{Colors.ENDC}")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\n{Colors.WARNING}Install with: pip install {' '.join(missing)}{Colors.ENDC}")
        return False
    
    print(f"{Colors.OKGREEN}[STARTUP] All dependencies found{Colors.ENDC}")
    return True


def check_database():
    """Check if PostgreSQL database is running"""
    print(f"{Colors.HEADER}[STARTUP] Checking database...{Colors.ENDC}")
    
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
        print(f"{Colors.OKGREEN}[STARTUP] Database connection OK{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] Database not available: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}Start with: docker compose up -d{Colors.ENDC}")
        return False


def print_banner():
    """Print startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║         GPS SIMULATION WITH JAMMING DETECTION             ║
    ║                                                           ║
    ║  Components:                                              ║
    ║    • Satellite Constellation (NMEA/RTCM Generator)        ║
    ║    • Multi-Agent Simulation (Movement & Jamming)          ║
    ║    • Requirements Monitor (GPS Denial Detection)          ║
    ║    • MCP Chatapp (LLM Control & RAG)                      ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(f"{Colors.HEADER}{banner}{Colors.ENDC}")


def main():
    """Main startup routine"""
    parser = argparse.ArgumentParser(description='Start integrated GPS simulation system')
    parser.add_argument('--no-gps', action='store_true', 
                       help='Skip satellite constellation server')
    parser.add_argument('--no-requirements', action='store_true',
                       help='Skip requirements monitoring')
    parser.add_argument('--no-simulation', action='store_true',
                       help='Skip agent simulation')
    parser.add_argument('--no-mcp', action='store_true',
                       help='Skip MCP chatapp')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check dependencies and exit')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check database
    if not check_database():
        sys.exit(1)
    
    if args.check_only:
        print(f"\n{Colors.OKGREEN}[STARTUP] All checks passed!{Colors.ENDC}")
        sys.exit(0)
    
    # Create process manager
    manager = ProcessManager()
    
    # Set up signal handler for clean shutdown
    def signal_handler(sig, frame):
        print(f"\n{Colors.WARNING}[SIGNAL] Received interrupt signal{Colors.ENDC}")
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 1. Start Satellite Constellation Server
        if not args.no_gps:
            process = manager.start_process(
                "Satellite Constellation",
                [sys.executable, "sat_constellation.py"],
                wait_time=3.0
            )
            if not process:
                print(f"{Colors.WARNING}[WARNING] Continuing without GPS constellation{Colors.ENDC}")
        
        # 2. Start Agent Simulation
        if not args.no_simulation:
            process = manager.start_process(
                "Agent Simulation",
                [sys.executable, "sim.py"],
                wait_time=3.0
            )
            if not process:
                print(f"{Colors.FAIL}[ERROR] Agent simulation is required{Colors.ENDC}")
                manager.stop_all()
                sys.exit(1)
        
        # 3. Start MCP Chatapp
        if not args.no_mcp:
            process = manager.start_process(
                "MCP Chatapp",
                [sys.executable, "mcp_chatapp.py"],
                wait_time=3.0
            )
            if not process:
                print(f"{Colors.WARNING}[WARNING] MCP chatapp failed to start{Colors.ENDC}")
        
        # Print success message
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}[STARTUP] All components started successfully!{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}Access points:{Colors.ENDC}")
        print(f"  • MCP Chatapp:          http://127.0.0.1:5000")
        print(f"  • Simulation API:       http://127.0.0.1:5001")
        print(f"  • Constellation Server: tcp://127.0.0.1:12345")
        print(f"\n{Colors.WARNING}Press Ctrl+C to stop all services{Colors.ENDC}\n")
        
        # Monitor processes
        while True:
            time.sleep(5)
            if not manager.check_health():
                print(f"{Colors.FAIL}[ERROR] One or more processes stopped{Colors.ENDC}")
                break
    
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()