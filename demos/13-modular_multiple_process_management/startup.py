#!/usr/bin/env python3
"""
Backend Services Launcher - Refactored
Coordinates startup of all backend services with better error handling
"""

import subprocess
import sys
import time
import signal
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class ServiceConfig:
    name: str
    command: List[str]
    port: Optional[int] = None
    startup_time: float = 2.0
    health_check: Optional[callable] = None


class Service:
    """Manages a single backend service"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.status = ServiceStatus.STOPPED
    
    def start(self) -> bool:
        """Start the service"""
        print(f"[SERVICE] Starting {self.config.name}...")
        self.status = ServiceStatus.STARTING
        
        try:
            self.process = subprocess.Popen(
                self.config.command,
                stdout=None,  # Let output print to console
                stderr=None,
                text=True
            )
            
            # Wait for startup
            time.sleep(0.5)
            
            # Check if process started successfully
            if self.process.poll() is not None:
                print(f"[ERROR] {self.config.name} failed to start")
                self.status = ServiceStatus.FAILED
                return False
            
            # Wait additional time for service to initialize
            if self.config.startup_time > 0.5:
                time.sleep(self.config.startup_time - 0.5)
            
            # Run health check if provided
            if self.config.health_check:
                if not self.config.health_check():
                    print(f"[WARNING] {self.config.name} health check failed")
                    self.status = ServiceStatus.FAILED
                    return False
            
            self.status = ServiceStatus.RUNNING
            print(f"[SUCCESS] {self.config.name} started (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to start {self.config.name}: {e}")
            self.status = ServiceStatus.FAILED
            return False
    
    def stop(self):
        """Stop the service"""
        if self.process and self.process.poll() is None:
            print(f"[SHUTDOWN] Stopping {self.config.name}...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print(f"[SUCCESS] {self.config.name} stopped")
            except subprocess.TimeoutExpired:
                print(f"[WARNING] Force killing {self.config.name}...")
                self.process.kill()
            finally:
                self.status = ServiceStatus.STOPPED
    
    def is_running(self) -> bool:
        """Check if service is still running"""
        if self.process:
            return self.process.poll() is None
        return False


class ServiceCoordinator:
    """Coordinates multiple backend services"""
    
    def __init__(self):
        self.services: List[Service] = []
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        print(f"\n[SIGNAL] Received interrupt signal")
        self.stop_all()
        sys.exit(0)
    
    def add_service(self, config: ServiceConfig) -> Service:
        """Add a service to be managed"""
        service = Service(config)
        self.services.append(service)
        return service
    
    def start_all(self) -> bool:
        """Start all services in order"""
        print("="*60)
        print("STARTING BACKEND SERVICES")
        print("="*60)
        
        all_started = True
        for service in self.services:
            if not service.start():
                all_started = False
                print(f"[WARNING] Continuing despite {service.config.name} failure")
        
        return all_started
    
    def stop_all(self):
        """Stop all services in reverse order"""
        print("\n[SHUTDOWN] Stopping all services...")
        
        for service in reversed(self.services):
            service.stop()
        
        print("[SHUTDOWN] All services stopped")
    
    def monitor(self):
        """Monitor services and keep running"""
        print("\n" + "="*60)
        print("BACKEND SERVICES RUNNING")
        print("="*60)
        print("\nPress Ctrl+C to shutdown\n")
        
        try:
            while True:
                # Check if any service has died
                for service in self.services:
                    if service.status == ServiceStatus.RUNNING and not service.is_running():
                        print(f"[ERROR] {service.config.name} has stopped unexpectedly!")
                        service.status = ServiceStatus.FAILED
                
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def check_dependencies() -> bool:
    """Verify required packages are installed"""
    print("[CHECK] Verifying dependencies...")
    
    required = ['fastapi', 'uvicorn', 'psycopg2', 'pynmea2', 'httpx']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"[ERROR] Missing packages: {', '.join(missing)}")
        print(f"[INFO] Install with: pip install {' '.join(missing)}")
        return False
    
    print("[SUCCESS] All dependencies found")
    return True


def check_database() -> bool:
    """Verify PostgreSQL is accessible"""
    print("[CHECK] Verifying database connection...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname="rag_db",
            user="postgres",
            password="password",
            host="localhost",
            port="5432",
            connect_timeout=3
        )
        conn.close()
        print("[SUCCESS] Database connection OK")
        return True
    except Exception as e:
        print(f"[ERROR] Database not available: {e}")
        print("[INFO] Start with: docker compose up -d")
        return False


def main():
    """Main entry point"""
    
    # Pre-flight checks
    if not check_dependencies():
        sys.exit(1)
    
    if not check_database():
        sys.exit(1)
    
    # Create service coordinator
    coordinator = ServiceCoordinator()
    
    # Add Simulation API Service
    coordinator.add_service(ServiceConfig(
        name="Simulation API",
        command=[sys.executable, "sim_api.py"],
        port=5001,
        startup_time=2.0
    ))
    
    # Add GPS Constellation Service
    coordinator.add_service(ServiceConfig(
        name="GPS Constellation",
        command=[sys.executable, "sat_constellation.py"],
        port=12345,
        startup_time=3.0
    ))
    
    # Add MCP Chatapp Service
    coordinator.add_service(ServiceConfig(
        name="MCP Chatapp",
        command=[sys.executable, "mcp_chatapp.py"],
        port=5000,
        startup_time=3.0
    ))
    
    # Start all services
    if not coordinator.start_all():
        print("\n[WARNING] Some services failed to start")
        print("[INFO] You can continue, but functionality may be limited")
    else:
        print("\n[SUCCESS] All services started successfully!")
    
    # Show access information
    print("\n" + "="*60)
    print("SERVICE ACCESS POINTS")
    print("="*60)
    print("  • MCP Chatapp:      http://localhost:5000")
    print("  • Simulation API:   http://localhost:5001")
    print("  • GPS Constellation: tcp://localhost:12345")
    print("\n[INFO] To start GUI, run: python main_gui.py")
    print("="*60 + "\n")
    
    # Monitor services
    coordinator.monitor()
    
    # Cleanup
    coordinator.stop_all()


if __name__ == "__main__":
    main()