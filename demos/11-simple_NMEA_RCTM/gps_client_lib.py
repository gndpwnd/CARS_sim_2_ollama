#!/usr/bin/env python3
"""
GPS Client Library

Client library for vehicles to communicate with the satellite constellation simulator.
Handles NMEA and RTCM message parsing and provides easy-to-use GPS data interface.

Dependencies:
    pip install pynmea2 pyrtcm
"""

import json
import socket
import threading
import time
from typing import Dict, List, Tuple, Any, Optional, Callable
from dataclasses import dataclass, asdict
import logging

import pynmea2
from pyrtcm import RTCMReader


@dataclass
class GPSFix:
    """GPS position fix information."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    fix_quality: int = 0  # 0=no fix, 1=GPS, 2=DGPS, 4=RTK fixed, 5=RTK float, 6=RTK fixed
    satellites_used: int = 0
    hdop: float = 99.9
    vdop: float = 99.9
    pdop: float = 99.9
    speed_kmh: float = 0.0
    heading: float = 0.0
    timestamp: str = ""
    valid: bool = False


@dataclass
class SatelliteInfo:
    """Information about a visible satellite."""
    prn: int = 0
    elevation: int = 0
    azimuth: int = 0
    snr: int = 0
    used_in_solution: bool = False
    constellation: str = "GPS"


@dataclass
class GPSStatus:
    """Overall GPS system status."""
    fix: GPSFix
    satellites: List[SatelliteInfo]
    signal_quality_avg: float = 0.0
    last_update: float = 0.0
    connection_active: bool = False
    error_message: str = ""


class GPSClient:
    """Client for communicating with satellite constellation simulator."""
    
    def __init__(self, vehicle_id: str, server_host: str = "localhost", 
                 server_port: int = 12345, update_rate_hz: float = 1.0):
        self.vehicle_id = vehicle_id
        self.server_host = server_host
        self.server_port = server_port
        self.update_rate_hz = update_rate_hz
        
        # Connection state
        self.socket = None
        self.connected = False
        self.running = False
        
        # GPS data
        self.current_status = GPSStatus(
            fix=GPSFix(),
            satellites=[]
        )
        
        # Vehicle state for requests
        self.vehicle_position = (0.0, 0.0, 0.0)  # lat, lon, alt
        self.vehicle_velocity = (0.0, 0.0)  # speed_ms, heading_deg
        self.gps_denied = False
        self.jamming_level = 0.0
        self.environmental_factor = 1.0
        
        # Threading
        self.update_thread = None
        self.data_lock = threading.Lock()
        
        # Callbacks
        self.fix_callback: Optional[Callable[[GPSFix], None]] = None
        self.satellite_callback: Optional[Callable[[List[SatelliteInfo]], None]] = None
        self.status_callback: Optional[Callable[[GPSStatus], None]] = None
        
        # Logging
        self.logger = logging.getLogger(f"GPSClient_{vehicle_id}")
        
    def connect(self) -> bool:
        """Connect to the satellite constellation server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5 second timeout
            self.socket.connect((self.server_host, self.server_port))
            
            self.connected = True
            self.current_status.connection_active = True
            self.logger.info(f"Connected to constellation server at {self.server_host}:{self.server_port}")
            
            return True
            
        except socket.error as e:
            self.logger.error(f"Failed to connect to constellation server: {e}")
            self.current_status.connection_active = False
            self.current_status.error_message = str(e)
            return False
    
    def disconnect(self):
        """Disconnect from the server."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        self.current_status.connection_active = False
        self.logger.info("Disconnected from constellation server")
    
    def start_updates(self):
        """Start automatic GPS data updates."""
        if self.running:
            return
        
        if not self.connected:
            if not self.connect():
                return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        self.logger.info(f"Started GPS updates at {self.update_rate_hz} Hz")
    
    def stop_updates(self):
        """Stop automatic GPS data updates."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2.0)
        
        self.disconnect()
        self.logger.info("Stopped GPS updates")
    
    def _update_loop(self):
        """Main update loop running in separate thread."""
        update_interval = 1.0 / self.update_rate_hz
        
        while self.running:
            try:
                # Request GPS data from constellation
                response = self._request_gps_data()
                
                if response and 'error' not in response:
                    # Parse response and update status
                    self._parse_constellation_response(response)
                else:
                    self.logger.warning(f"GPS data request failed: {response.get('error', 'Unknown error')}")
                    self.current_status.error_message = response.get('error', 'Communication error')
                
            except Exception as e:
                self.logger.error(f"Update loop error: {e}")
                self.current_status.error_message = str(e)
                self.current_status.connection_active = False
                
                # Try to reconnect
                self.disconnect()
                time.sleep(1.0)
                if not self.connect():
                    time.sleep(5.0)  # Wait longer before retry
                    continue
            
            time.sleep(update_interval)
    
    def _request_gps_data(self) -> Optional[Dict[str, Any]]:
        """Request GPS data from constellation server."""
        if not self.socket or not self.connected:
            return None
        
        # Prepare request
        request = {
            'vehicle_id': self.vehicle_id,
            'latitude': self.vehicle_position[0],
            'longitude': self.vehicle_position[1], 
            'altitude': self.vehicle_position[2],
            'speed': self.vehicle_velocity[0],
            'heading': self.vehicle_velocity[1],
            'gps_denied': self.gps_denied,
            'jamming_level': self.jamming_level,
            'environmental_factor': self.environmental_factor,
            'timestamp': time.time()
        }
        
        try:
            # Send request
            request_data = json.dumps(request).encode('utf-8')
            self.socket.send(request_data)
            
            # Receive response
            response_data = self.socket.recv(8192)
            if not response_data:
                return None
            
            response = json.loads(response_data.decode('utf-8'))
            return response
            
        except (socket.error, json.JSONDecodeError) as e:
            self.logger.error(f"Communication error: {e}")
            self.connected = False
            return None
    
    def _parse_constellation_response(self, response: Dict[str, Any]):
        """Parse response from constellation and update GPS status."""
        with self.data_lock:
            try:
                # Parse NMEA sentences
                nmea_sentences = response.get('nmea_sentences', [])
                self._parse_nmea_sentences(nmea_sentences)
                
                # Parse RTCM messages (if needed)
                rtcm_messages = response.get('rtcm_messages', [])
                self._parse_rtcm_messages(rtcm_messages)
                
                # Update overall status
                self.current_status.last_update = time.time()
                self.current_status.connection_active = True
                self.current_status.error_message = ""
                self.current_status.signal_quality_avg = response.get('signal_quality', 0.0)
                
                # Trigger callbacks
                self._trigger_callbacks()
                
            except Exception as e:
                self.logger.error(f"Error parsing constellation response: {e}")
                self.current_status.error_message = str(e)
    
    def _parse_nmea_sentences(self, sentences: List[str]):
        """Parse NMEA sentences and update GPS fix data."""
        satellites_temp = {}
        
        for sentence_str in sentences:
            try:
                sentence = pynmea2.parse(sentence_str)
                
                if isinstance(sentence, pynmea2.GGA):
                    # Global Positioning System Fix Data
                    self.current_status.fix.latitude = float(sentence.latitude) if sentence.latitude else 0.0
                    self.current_status.fix.longitude = float(sentence.longitude) if sentence.longitude else 0.0
                    if sentence.lat_dir == 'S':
                        self.current_status.fix.latitude = -self.current_status.fix.latitude
                    if sentence.lon_dir == 'W':
                        self.current_status.fix.longitude = -self.current_status.fix.longitude
                    
                    self.current_status.fix.altitude = float(sentence.altitude) if sentence.altitude else 0.0
                    self.current_status.fix.fix_quality = int(sentence.gps_qual) if sentence.gps_qual else 0
                    self.current_status.fix.satellites_used = int(sentence.num_sats) if sentence.num_sats else 0
                    self.current_status.fix.hdop = float(sentence.horizontal_dil) if sentence.horizontal_dil else 99.9
                    self.current_status.fix.timestamp = sentence.timestamp if sentence.timestamp else ""
                    self.current_status.fix.valid = sentence.gps_qual and int(sentence.gps_qual) > 0
                
                elif isinstance(sentence, pynmea2.RMC):
                    # Recommended Minimum Navigation Information
                    if sentence.spd_over_grnd:
                        self.current_status.fix.speed_kmh = float(sentence.spd_over_grnd) * 1.852  # knots to km/h
                    if sentence.true_course:
                        self.current_status.fix.heading = float(sentence.true_course)
                
                elif isinstance(sentence, pynmea2.GSA):
                    # GPS DOP and Active Satellites
                    if sentence.pdop:
                        self.current_status.fix.pdop = float(sentence.pdop)
                    if sentence.hdop:
                        self.current_status.fix.hdop = float(sentence.hdop)
                    if sentence.vdop:
                        self.current_status.fix.vdop = float(sentence.vdop)
                
                elif isinstance(sentence, pynmea2.GSV):
                    # GPS Satellites in View
                    for i in range(1, 5):  # Up to 4 satellites per GSV sentence
                        prn_attr = f"sv_{i:02d}_prn"
                        elev_attr = f"sv_{i:02d}_elev"
                        az_attr = f"sv_{i:02d}_az"
                        snr_attr = f"sv_{i:02d}_snr"
                        
                        if hasattr(sentence, prn_attr):
                            prn = getattr(sentence, prn_attr)
                            if prn and prn.strip():
                                sat_info = SatelliteInfo(
                                    prn=int(prn),
                                    elevation=int(getattr(sentence, elev_attr, 0) or 0),
                                    azimuth=int(getattr(sentence, az_attr, 0) or 0),
                                    snr=int(getattr(sentence, snr_attr, 0) or 0),
                                    constellation="GPS"
                                )
                                satellites_temp[sat_info.prn] = sat_info
                
            except (ValueError, AttributeError) as e:
                self.logger.warning(f"Error parsing NMEA sentence '{sentence_str}': {e}")
                continue
        
        # Update satellites list
        self.current_status.satellites = list(satellites_temp.values())
        
        # Mark satellites used in solution
        # (This would typically come from GSA sentences, but we'll approximate)
        sorted_sats = sorted(self.current_status.satellites, key=lambda s: s.snr, reverse=True)
        num_used = min(self.current_status.fix.satellites_used, len(sorted_sats))
        for i in range(num_used):
            sorted_sats[i].used_in_solution = True
    
    def _parse_rtcm_messages(self, messages: List[str]):
        """Parse RTCM messages (currently just logs them)."""
        # RTCM parsing is complex and would require full implementation
        # For now, we just log that we received them
        if messages:
            self.logger.debug(f"Received {len(messages)} RTCM messages")
    
    def _trigger_callbacks(self):
        """Trigger registered callbacks with updated data."""
        try:
            if self.fix_callback:
                self.fix_callback(self.current_status.fix)
            
            if self.satellite_callback:
                self.satellite_callback(self.current_status.satellites)
            
            if self.status_callback:
                self.status_callback(self.current_status)
                
        except Exception as e:
            self.logger.error(f"Error in callback: {e}")
    
    def update_vehicle_state(self, latitude: float, longitude: float, altitude: float = 0.0,
                           speed_ms: float = 0.0, heading_deg: float = 0.0):
        """Update vehicle position and motion for GPS requests."""
        self.vehicle_position = (latitude, longitude, altitude)
        self.vehicle_velocity = (speed_ms, heading_deg)
    
    def set_gps_conditions(self, gps_denied: bool = False, jamming_level: float = 0.0,
                         environmental_factor: float = 1.0):
        """Set GPS environmental conditions."""
        self.gps_denied = gps_denied
        self.jamming_level = max(0.0, min(100.0, jamming_level))
        self.environmental_factor = max(0.0, min(2.0, environmental_factor))
    
    def get_current_fix(self) -> GPSFix:
        """Get current GPS fix data."""
        with self.data_lock:
            return GPSFix(**asdict(self.current_status.fix))
    
    def get_satellites(self) -> List[SatelliteInfo]:
        """Get current satellite information."""
        with self.data_lock:
            return [SatelliteInfo(**asdict(sat)) for sat in self.current_status.satellites]
    
    def get_status(self) -> GPSStatus:
        """Get complete GPS status."""
        with self.data_lock:
            return GPSStatus(
                fix=GPSFix(**asdict(self.current_status.fix)),
                satellites=[SatelliteInfo(**asdict(sat)) for sat in self.current_status.satellites],
                signal_quality_avg=self.current_status.signal_quality_avg,
                last_update=self.current_status.last_update,
                connection_active=self.current_status.connection_active,
                error_message=self.current_status.error_message
            )
    
    def is_fix_valid(self) -> bool:
        """Check if current GPS fix is valid."""
        with self.data_lock:
            return (self.current_status.fix.valid and 
                    self.current_status.fix.fix_quality > 0 and
                    self.current_status.connection_active)
    
    def get_position_accuracy_estimate(self) -> float:
        """Estimate position accuracy in meters based on HDOP and fix quality."""
        with self.data_lock:
            fix = self.current_status.fix
            
            if not fix.valid:
                return float('inf')
            
            # Base accuracy estimates by fix type
            base_accuracy = {
                0: float('inf'),  # No fix
                1: 5.0,          # GPS SPS
                2: 3.0,          # DGPS
                4: 1.0,          # RTK Fixed
                5: 2.0,          # RTK Float
                6: 0.1           # RTK Fixed (high precision)
            }.get(fix.fix_quality, 10.0)
            
            # Scale by HDOP
            hdop_factor = max(1.0, fix.hdop)
            
            return base_accuracy * hdop_factor
    
    def set_fix_callback(self, callback: Callable[[GPSFix], None]):
        """Set callback for GPS fix updates."""
        self.fix_callback = callback
    
    def set_satellite_callback(self, callback: Callable[[List[SatelliteInfo]], None]):
        """Set callback for satellite data updates."""
        self.satellite_callback = callback
    
    def set_status_callback(self, callback: Callable[[GPSStatus], None]):
        """Set callback for overall status updates."""
        self.status_callback = callback
    
    def get_nmea_sentence_raw(self) -> Optional[str]:
        """Request a single raw NMEA sentence for testing."""
        if not self.connected:
            return None
        
        try:
            response = self._request_gps_data()
            if response and 'nmea_sentences' in response:
                sentences = response['nmea_sentences']
                return sentences[0] if sentences else None
        except Exception as e:
            self.logger.error(f"Error getting raw NMEA: {e}")
        
        return None


class GPSClientManager:
    """Manager for multiple GPS clients."""
    
    def __init__(self):
        self.clients: Dict[str, GPSClient] = {}
        
    def create_client(self, vehicle_id: str, **kwargs) -> GPSClient:
        """Create and register a new GPS client."""
        if vehicle_id in self.clients:
            self.clients[vehicle_id].stop_updates()
        
        client = GPSClient(vehicle_id, **kwargs)
        self.clients[vehicle_id] = client
        return client
    
    def get_client(self, vehicle_id: str) -> Optional[GPSClient]:
        """Get existing client by vehicle ID."""
        return self.clients.get(vehicle_id)
    
    def remove_client(self, vehicle_id: str):
        """Remove and stop a client."""
        if vehicle_id in self.clients:
            self.clients[vehicle_id].stop_updates()
            del self.clients[vehicle_id]
    
    def start_all(self):
        """Start updates for all clients."""
        for client in self.clients.values():
            client.start_updates()
    
    def stop_all(self):
        """Stop updates for all clients."""
        for client in self.clients.values():
            client.stop_updates()
    
    def get_all_status(self) -> Dict[str, GPSStatus]:
        """Get status from all clients."""
        return {vid: client.get_status() for vid, client in self.clients.items()}


# Example usage and testing
def example_usage():
    """Example of how to use the GPS client."""
    
    # Create client
    client = GPSClient("test_vehicle_1", update_rate_hz=2.0)
    
    # Set up callbacks
    def on_fix_update(fix: GPSFix):
        print(f"Position: {fix.latitude:.6f}, {fix.longitude:.6f}, Quality: {fix.fix_quality}")
    
    def on_satellite_update(satellites: List[SatelliteInfo]):
        print(f"Satellites: {len(satellites)} visible")
    
    client.set_fix_callback(on_fix_update)
    client.set_satellite_callback(on_satellite_update)
    
    # Update vehicle position (would come from vehicle simulation)
    client.update_vehicle_state(40.7128, -74.0060, 10.0, 5.0, 45.0)
    
    # Start receiving GPS data
    client.start_updates()
    
    try:
        # Simulate vehicle movement and different conditions
        for i in range(10):
            time.sleep(1)
            
            # Simulate movement
            lat = 40.7128 + i * 0.0001
            lon = -74.0060 + i * 0.0001
            client.update_vehicle_state(lat, lon, 10.0, 2.0, 90.0)
            
            # Simulate different GPS conditions
            if i == 5:
                client.set_gps_conditions(jamming_level=50.0)  # Simulate jamming
            elif i == 8:
                client.set_gps_conditions(gps_denied=True)     # Simulate GPS denial
            
            # Check status
            status = client.get_status()
            print(f"Connection: {status.connection_active}, Fix valid: {status.fix.valid}")
    
    finally:
        client.stop_updates()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run example
    example_usage()