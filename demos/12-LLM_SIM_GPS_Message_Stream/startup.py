#!/usr/bin/env python3
"""
Integrated GPS Simulation Startup Script - Fixed for WSL2 GUI Support

Starts all components in the correct order with proper GUI handling:
1. Satellite Constellation Server (background)
2. MCP Chatapp (background)
3. Agent Simulation with matplotlib GUI (main thread)

Usage:
    python startup.py [--no-gps] [--no-mcp] [--headless]
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
                     wait_time: float = 2.0, show_output: bool = False) -> Optional[subprocess.Popen]:
        """
        Start a subprocess and track it
        
        Args:
            name: Process name for logging
            command: Command and arguments to execute
            wait_time: Time to wait after starting
            show_output: Whether to show stdout/stderr
            
        Returns:
            Subprocess object or None if failed
        """
        print(f"{Colors.OKBLUE}[STARTUP] Starting {name}...{Colors.ENDC}")
        
        try:
            if show_output:
                process = subprocess.Popen(command)
            else:
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
                if not show_output:
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


def check_display():
    """Check if DISPLAY is set for WSL2"""
    display = os.environ.get('DISPLAY')
    if not display:
        print(f"{Colors.WARNING}[WARNING] DISPLAY not set. GUIs may not work.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}[INFO] For WSL2, set DISPLAY with:{Colors.ENDC}")
        print(f"  export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0")
        print(f"  # Or use a X server like VcXsrv, Xming, or WSLg{Colors.ENDC}")
        return False
    else:
        print(f"{Colors.OKGREEN}[STARTUP] DISPLAY is set to: {display}{Colors.ENDC}")
        return True


def print_banner():
    """Print startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║         GPS SIMULATION WITH JAMMING DETECTION             ║
    ║                                                           ║
    ║  Components:                                              ║
    ║    • Satellite Constellation (NMEA/RTCM Generator)        ║
    ║    • Multi-Agent Simulation (matplotlib GUI)              ║
    ║    • Requirements Monitor (Optional PyQt5 Dashboard)      ║
    ║    • MCP Chatapp (Web Interface + RAG)                    ║
    ║                                                           ║
    ║  GUI Notes for WSL2:                                      ║
    ║    • matplotlib GUI runs in main thread                   ║
    ║    • Click 'Show Dashboard' for Requirements Board        ║
    ║    • Web interface at http://localhost:5000               ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(f"{Colors.HEADER}{banner}{Colors.ENDC}")


def main():
    """Main startup routine"""
    parser = argparse.ArgumentParser(description='Start integrated GPS simulation system')
    parser.add_argument('--no-gps', action='store_true', 
                       help='Skip satellite constellation server')
    parser.add_argument('--no-mcp', action='store_true',
                       help='Skip MCP chatapp')
    parser.add_argument('--headless', action='store_true',
                       help='Run simulation without GUI (not recommended)')
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
    
    # Check display (warning only, not fatal)
    display_ok = check_display()
    if not display_ok and not args.headless:
        print(f"{Colors.WARNING}[WARNING] Continuing anyway, but GUI may not display{Colors.ENDC}")
        time.sleep(2)
    
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
        # 1. Start Satellite Constellation Server (background)
        if not args.no_gps:
            process = manager.start_process(
                "Satellite Constellation",
                [sys.executable, "sat_constellation.py"],
                wait_time=3.0,
                show_output=False
            )
            if not process:
                print(f"{Colors.WARNING}[WARNING] Continuing without GPS constellation{Colors.ENDC}")
        
        # 2. Start MCP Chatapp (background)
        if not args.no_mcp:
            process = manager.start_process(
                "MCP Chatapp",
                [sys.executable, "mcp_chatapp.py"],
                wait_time=3.0,
                show_output=False
            )
            if not process:
                print(f"{Colors.WARNING}[WARNING] MCP chatapp failed to start{Colors.ENDC}")
        
        # Print access information
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}[STARTUP] Backend services started!{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}Access points:{Colors.ENDC}")
        print(f"  • MCP Chatapp:          http://localhost:5000")
        print(f"  • Simulation API:       http://localhost:5001")
        print(f"  • Constellation Server: tcp://localhost:12345")
        
        # 3. Start Agent Simulation with matplotlib GUI (MAIN THREAD - BLOCKING)
        print(f"\n{Colors.OKGREEN}[STARTUP] Starting Agent Simulation with GUI...{Colors.ENDC}")
        print(f"{Colors.OKCYAN}[INFO] matplotlib window should appear shortly{Colors.ENDC}")
        print(f"{Colors.OKCYAN}[INFO] Click 'Show Dashboard' button for Requirements Board{Colors.ENDC}")
        print(f"{Colors.WARNING}[INFO] Close the matplotlib window to shutdown all services{Colors.ENDC}\n")
        
        time.sleep(1)
        
        # Run simulation in main thread (this blocks until GUI is closed)
        if args.headless:
            print(f"{Colors.WARNING}[HEADLESS] Running without GUI - press Ctrl+C to stop{Colors.ENDC}")
            import sim
            sim.initialize_agents()
            while True:
                time.sleep(1)
        else:
            # Import and run simulation with GUI
            import sim
            
            # The simulation will run and block here until matplotlib window is closed
            sim.main()
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR] Unexpected error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()