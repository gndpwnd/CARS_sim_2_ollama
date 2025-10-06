#!/usr/bin/env python3
"""
GPS Client Integration for Agent Simulation

Connects agents to the satellite constellation server to receive
GPS data based on their position and environmental conditions.
"""

import socket
import json
import threading
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
import math


@dataclass
class GPSData:
    """Stores GPS data received from constellation"""
    vehicle_id: str
    nmea_sentences: list
    rtcm_messages: list
    satellite_count: int
    fix_quality: int
    signal_quality: float
    timestamp: float
    valid: bool = True


class GPSClient:
    """Client for requesting GPS data from satellite constellation"""
    
    def __init__(self, constellation_host: str = "localhost", 
                 constellation_port: int = 12345):
        self.host = constellation_host
        self.port = constellation_port
        self.socket = None
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to satellite constellation server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to satellite constellation at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to satellite constellation: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from satellite constellation"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
    
    def request_gps_data(self, vehicle_id: str, latitude: float, longitude: float,
                        altitude: float = 10.0, speed: float = 0.0, heading: float = 0.0,
                        gps_denied: bool = False, jamming_level: float = 0.0,
                        environmental_factor: float = 1.0) -> Optional[GPSData]:
        """
        Request GPS data from satellite constellation
        
        Args:
            vehicle_id: Unique identifier for the vehicle/agent
            latitude: Current latitude in degrees
            longitude: Current longitude in degrees
            altitude: Current altitude in meters
            speed: Current speed in m/s
            heading: Current heading in degrees
            gps_denied: Whether GPS is completely denied
            jamming_level: Jamming intensity (0-100%)
            environmental_factor: Environmental signal degradation factor
            
        Returns:
            GPSData object or None if request failed
        """
        if not self.connected:
            if not self.connect():
                return None
        
        # Prepare request
        request = {
            "vehicle_id": vehicle_id,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "speed": speed,
            "heading": heading,
            "gps_denied": gps_denied,
            "jamming_level": jamming_level,
            "environmental_factor": environmental_factor
        }
        
        try:
            # Send request
            request_data = json.dumps(request).encode('utf-8')
            self.socket.send(request_data)
            
            # Receive response
            response_data = self.socket.recv(8192)
            if not response_data:
                self.connected = False
                return None
            
            response = json.loads(response_data.decode('utf-8'))
            
            # Check for error
            if 'error' in response:
                print(f"GPS request error: {response['error']}")
                return None
            
            # Create GPSData object
            gps_data = GPSData(
                vehicle_id=response['vehicle_id'],
                nmea_sentences=response['nmea_sentences'],
                rtcm_messages=response['rtcm_messages'],
                satellite_count=response['satellite_count'],
                fix_quality=response['fix_quality'],
                signal_quality=response['signal_quality'],
                timestamp=response['timestamp']
            )
            
            return gps_data
            
        except Exception as e:
            print(f"GPS request failed: {e}")
            self.connected = False
            return None


class AgentGPSManager:
    """Manages GPS data requests for all agents in simulation"""
    
    def __init__(self, constellation_host: str = "localhost",
                 constellation_port: int = 12345,
                 base_latitude: float = 40.7128,
                 base_longitude: float = -74.0060):
        self.gps_client = GPSClient(constellation_host, constellation_port)
        self.base_latitude = base_latitude
        self.base_longitude = base_longitude
        self.gps_data_cache: Dict[str, GPSData] = {}
        self.update_interval = 1.0  # Update GPS data every second
        self.running = False
        self.update_thread = None
        
    def convert_xy_to_latlon(self, x: float, y: float) -> tuple:
        """
        Convert simulation X,Y coordinates to lat/lon
        Assumes 1 unit = ~100 meters for simplicity
        """
        # Rough conversion: 1 degree latitude ~ 111km
        # 1 degree longitude ~ 111km * cos(latitude)
        
        meters_per_degree_lat = 111000
        meters_per_degree_lon = 111000 * math.cos(math.radians(self.base_latitude))
        
        # Assuming 1 simulation unit = 100 meters
        meters_per_unit = 100
        
        lat_offset = (y * meters_per_unit) / meters_per_degree_lat
        lon_offset = (x * meters_per_unit) / meters_per_degree_lon
        
        latitude = self.base_latitude + lat_offset
        longitude = self.base_longitude + lon_offset
        
        return latitude, longitude
    
    def calculate_jamming_level(self, position: tuple, jamming_center: tuple,
                               jamming_radius: float) -> float:
        """
        Calculate jamming level based on distance from jamming center
        Returns jamming percentage (0-100%)
        """
        x, y = position
        cx, cy = jamming_center
        distance = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        if distance >= jamming_radius:
            return 0.0
        
        # Linear falloff from center
        jamming_level = 100 * (1 - distance / jamming_radius)
        return max(0.0, min(100.0, jamming_level))
    
    def update_agent_gps(self, agent_id: str, position: tuple,
                        jamming_center: tuple, jamming_radius: float,
                        gps_denied: bool = False) -> Optional[GPSData]:
        """
        Update GPS data for a specific agent
        
        Args:
            agent_id: Agent identifier
            position: (x, y) position in simulation coordinates
            jamming_center: Center of jamming zone
            jamming_radius: Radius of jamming zone
            gps_denied: Whether GPS is completely denied
            
        Returns:
            GPSData object or None if update failed
        """
        # Convert position to lat/lon
        latitude, longitude = self.convert_xy_to_latlon(position[0], position[1])
        
        # Calculate jamming level
        jamming_level = self.calculate_jamming_level(position, jamming_center, jamming_radius)
        
        # Request GPS data
        gps_data = self.gps_client.request_gps_data(
            vehicle_id=agent_id,
            latitude=latitude,
            longitude=longitude,
            altitude=10.0,
            speed=0.0,
            heading=0.0,
            gps_denied=gps_denied or jamming_level > 90,
            jamming_level=jamming_level,
            environmental_factor=1.0
        )
        
        if gps_data:
            self.gps_data_cache[agent_id] = gps_data
            
        return gps_data
    
    def get_gps_data(self, agent_id: str) -> Optional[GPSData]:
        """Get cached GPS data for an agent"""
        return self.gps_data_cache.get(agent_id)
    
    def start(self):
        """Start GPS manager"""
        if not self.running:
            self.running = True
            print("AgentGPSManager started")
    
    def stop(self):
        """Stop GPS manager"""
        self.running = False
        self.gps_client.disconnect()
        print("AgentGPSManager stopped")


def parse_nmea_gga(gga_sentence: str) -> Dict[str, Any]:
    """
    Parse NMEA GGA sentence to extract key information
    
    Returns dict with: fix_quality, satellites, hdop, altitude
    """
    try:
        parts = gga_sentence.split(',')
        if len(parts) < 15:
            return {}
        
        return {
            'time': parts[1],
            'latitude': parts[2],
            'lat_dir': parts[3],
            'longitude': parts[4],
            'lon_dir': parts[5],
            'fix_quality': int(parts[6]) if parts[6] else 0,
            'satellites': int(parts[7]) if parts[7] else 0,
            'hdop': float(parts[8]) if parts[8] else 99.9,
            'altitude': float(parts[9]) if parts[9] else 0.0,
            'valid': True
        }
    except Exception as e:
        print(f"Error parsing GGA: {e}")
        return {'valid': False}


# Example usage
if __name__ == "__main__":
    # Create GPS manager
    gps_manager = AgentGPSManager()
    gps_manager.start()
    
    # Simulate agent positions
    test_positions = {
        "agent1": (0, 0),
        "agent2": (5, 5),
        "agent3": (-3, 4)
    }
    
    jamming_center = (0, 0)
    jamming_radius = 5
    
    # Request GPS data for each agent
    for agent_id, position in test_positions.items():
        gps_data = gps_manager.update_agent_gps(
            agent_id, position, jamming_center, jamming_radius
        )
        
        if gps_data:
            print(f"\n{agent_id} GPS Data:")
            print(f"  Fix Quality: {gps_data.fix_quality}")
            print(f"  Satellites: {gps_data.satellite_count}")
            print(f"  Signal Quality: {gps_data.signal_quality:.2f}")
            print(f"  NMEA Sentences: {len(gps_data.nmea_sentences)}")
            
            # Parse first GGA sentence if available
            for sentence in gps_data.nmea_sentences:
                if 'GGA' in sentence:
                    parsed = parse_nmea_gga(sentence)
                    if parsed.get('valid'):
                        print(f"  Parsed GGA: {parsed}")
                    break
    
    gps_manager.stop()