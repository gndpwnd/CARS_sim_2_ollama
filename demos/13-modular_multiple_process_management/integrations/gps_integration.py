"""
GPS integration wrapper for satellite constellation.
"""
from typing import Optional
from core.config import GPS_CONSTELLATION_HOST, GPS_CONSTELLATION_PORT
from core.config import GPS_BASE_LATITUDE, GPS_BASE_LONGITUDE

# Try to import GPS client
try:
    from gps_client_lib import GPSData, AgentGPSManager, parse_nmea_gga
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    print("[GPS] GPS integration not available")
    GPSData = None
    AgentGPSManager = None
    parse_nmea_gga = None

class GPSManagerWrapper:
    """Wrapper for GPS manager with fallback"""
    
    def __init__(self, 
                 host: str = GPS_CONSTELLATION_HOST,
                 port: int = GPS_CONSTELLATION_PORT,
                 base_lat: float = GPS_BASE_LATITUDE,
                 base_lon: float = GPS_BASE_LONGITUDE):
        """
        Initialize GPS manager wrapper.
        
        Args:
            host: GPS constellation server host
            port: GPS constellation server port
            base_lat: Base latitude for coordinate conversion
            base_lon: Base longitude for coordinate conversion
        """
        self.manager = None
        self.enabled = GPS_AVAILABLE
        
        if GPS_AVAILABLE:
            try:
                self.manager = AgentGPSManager(
                    constellation_host=host,
                    constellation_port=port,
                    base_latitude=base_lat,
                    base_longitude=base_lon
                )
                print(f"[GPS] GPS manager created for {host}:{port}")
            except Exception as e:
                print(f"[GPS] Failed to create manager: {e}")
                self.enabled = False
    
    def start(self) -> bool:
        """Start GPS manager"""
        if self.manager:
            try:
                self.manager.start()
                print("[GPS] GPS manager started")
                return True
            except Exception as e:
                print(f"[GPS] Failed to start: {e}")
                return False
        return False
    
    def stop(self):
        """Stop GPS manager"""
        if self.manager:
            try:
                self.manager.stop()
                print("[GPS] GPS manager stopped")
            except Exception as e:
                print(f"[GPS] Error stopping: {e}")
    
    def update_agent_gps(self, 
                        agent_id: str,
                        position: tuple,
                        jamming_center: tuple,
                        jamming_radius: float,
                        gps_denied: bool = False) -> Optional[object]:
        """
        Update GPS data for an agent.
        
        Args:
            agent_id: Agent identifier
            position: Agent position (x, y)
            jamming_center: Jamming zone center
            jamming_radius: Jamming zone radius
            gps_denied: Whether GPS is denied
            
        Returns:
            GPSData object or None
        """
        if not self.manager:
            return None
        
        try:
            gps_data = self.manager.update_agent_gps(
                agent_id=agent_id,
                position=position,
                jamming_center=jamming_center,
                jamming_radius=jamming_radius,
                gps_denied=gps_denied
            )
            return gps_data
        except Exception as e:
            print(f"[GPS] Error updating agent {agent_id}: {e}")
            return None
    
    def is_enabled(self) -> bool:
        """Check if GPS is enabled and working"""
        return self.enabled and self.manager is not None

def create_gps_manager() -> Optional[GPSManagerWrapper]:
    """
    Create GPS manager with default configuration.
    
    Returns:
        GPSManagerWrapper or None if unavailable
    """
    if not GPS_AVAILABLE:
        return None
    
    return GPSManagerWrapper()