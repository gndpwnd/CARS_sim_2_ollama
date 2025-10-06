#!/usr/bin/env python3
"""
Fixed Satellite Constellation Simulator

Generates realistic NMEA sentences and RTCM messages based on vehicle position
and environmental conditions. Fixed NMEA sentence generation issues.

Dependencies:
    pip install pynmea2 pyrtcm
"""

import json
import math
import random
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
import struct

import pynmea2


@dataclass
class SatelliteInfo:
    """Information about a single satellite."""
    prn: int  # Pseudo-random number (satellite ID)
    elevation: float  # degrees above horizon
    azimuth: float  # degrees from north
    snr: float  # Signal-to-noise ratio (C/N0)
    used_in_solution: bool = False
    constellation: str = "GPS"  # GPS, GLONASS, Galileo, etc.


@dataclass
class VehicleState:
    """Current state of a vehicle requesting GPS data."""
    vehicle_id: str
    latitude: float  # degrees
    longitude: float  # degrees
    altitude: float  # meters
    speed: float  # m/s
    heading: float  # degrees
    last_request_time: float
    gps_denied: bool = False
    jamming_level: float = 0.0  # 0-100%
    environmental_factor: float = 1.0  # multiplier for signal quality


class SatelliteConstellation:
    """Simulates a GPS/GNSS satellite constellation."""
    
    def __init__(self, config_file: str = "constellation_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        
        # Simulation state
        self.simulation_start_time = time.time()
        self.vehicle_states: Dict[str, VehicleState] = {}
        
        # Generate satellite constellation
        self.satellites = self._generate_satellite_constellation()
        
        # Environmental conditions
        self.ionospheric_activity = 1.0
        self.tropospheric_delay = 0.0
        self.multipath_factor = 1.0
        
        # Server state
        self.server_socket = None
        self.running = False
        self.clients = []
        
    def load_config(self) -> Dict[str, Any]:
        """Load constellation configuration."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default configuration
            return {
                "gps_satellites": 32,
                "glonass_satellites": 24,
                "galileo_satellites": 30,
                "base_station": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "altitude": 10.0
                },
                "server": {
                    "host": "localhost",
                    "port": 12345
                },
                "signal_quality": {
                    "base_cnr": 45.0,
                    "noise_floor": 20.0,
                    "jamming_threshold": 70.0
                }
            }
    
    def _generate_satellite_constellation(self) -> List[SatelliteInfo]:
        """Generate a realistic satellite constellation."""
        satellites = []
        
        # GPS satellites (PRN 1-32)
        for prn in range(1, min(33, self.config["gps_satellites"] + 1)):
            sat = SatelliteInfo(
                prn=prn,
                elevation=random.uniform(10, 85),
                azimuth=random.uniform(0, 360),
                snr=random.uniform(35, 50),
                constellation="GPS"
            )
            satellites.append(sat)
        
        return satellites
    
    def update_satellite_positions(self, simulation_time: float):
        """Update satellite positions based on orbital motion."""
        for sat in self.satellites:
            # Simulate orbital motion (simplified)
            time_factor = simulation_time / 43200  # 12-hour orbit approximation
            
            # Update elevation and azimuth with realistic orbital motion
            sat.elevation += math.sin(time_factor + sat.prn) * 0.1
            sat.azimuth = (sat.azimuth + 0.25) % 360  # Slow westward motion
            
            # Keep elevation within reasonable bounds
            sat.elevation = max(5, min(85, sat.elevation))
    
    def calculate_signal_quality(self, vehicle_state: VehicleState, satellite: SatelliteInfo) -> float:
        """Calculate signal quality for a satellite as seen by a vehicle."""
        base_snr = self.config["signal_quality"]["base_cnr"]
        
        # Elevation mask - lower satellites have weaker signals
        elevation_factor = math.sin(math.radians(max(10, satellite.elevation)))
        
        # Environmental factors
        ionospheric_effect = 1.0 - (self.ionospheric_activity - 1.0) * 0.1
        multipath_effect = 1.0 - self.multipath_factor * 0.05
        
        # Jamming effect
        jamming_effect = 1.0 - (vehicle_state.jamming_level / 100.0) * 0.8
        
        # GPS denial (complete signal loss)
        if vehicle_state.gps_denied:
            return 0.0
        
        # Calculate final SNR
        final_snr = (base_snr * elevation_factor * ionospheric_effect * 
                    multipath_effect * jamming_effect * vehicle_state.environmental_factor)
        
        # Add some random variation
        final_snr += random.uniform(-2, 2)
        
        return max(0, final_snr)
    
    def get_visible_satellites(self, vehicle_state: VehicleState) -> List[SatelliteInfo]:
        """Get satellites visible to a vehicle with updated signal quality."""
        visible_sats = []
        
        for sat in self.satellites:
            # Calculate signal quality
            snr = self.calculate_signal_quality(vehicle_state, sat)
            
            # Only include satellites above elevation mask and with sufficient signal
            if sat.elevation > 10 and snr > 25:
                visible_sat = SatelliteInfo(
                    prn=sat.prn,
                    elevation=sat.elevation,
                    azimuth=sat.azimuth,
                    snr=snr,
                    constellation=sat.constellation
                )
                visible_sats.append(visible_sat)
        
        return visible_sats
    
    def select_satellites_for_solution(self, visible_sats: List[SatelliteInfo], 
                                     max_sats: int = 12) -> List[SatelliteInfo]:
        """Select best satellites for position solution."""
        # Sort by signal strength
        sorted_sats = sorted(visible_sats, key=lambda s: s.snr, reverse=True)
        
        # Select up to max_sats satellites
        selected = sorted_sats[:max_sats]
        
        # Mark as used in solution
        for sat in selected:
            sat.used_in_solution = True
            
        return selected
    
    def generate_nmea_sentences(self, vehicle_state: VehicleState) -> List[str]:
        """Generate NMEA sentences for a vehicle."""
        sentences = []
        simulation_time = time.time() - self.simulation_start_time
        
        # Update satellite positions
        self.update_satellite_positions(simulation_time)
        
        # Get visible satellites
        visible_sats = self.get_visible_satellites(vehicle_state)
        solution_sats = self.select_satellites_for_solution(visible_sats)
        
        # Generate current UTC time
        utc_time = datetime.now(timezone.utc)
        time_str = utc_time.strftime("%H%M%S.%f")[:-3]  # HHMMSS.sss
        date_str = utc_time.strftime("%d%m%y")  # DDMMYY
        
        # Determine fix quality
        num_sats = len(solution_sats)
        if num_sats >= 6 and not vehicle_state.gps_denied:
            fix_quality = 6  # RTK fixed
        elif num_sats >= 4 and not vehicle_state.gps_denied:
            fix_quality = 4  # DGPS
        elif num_sats >= 3:
            fix_quality = 1  # GPS SPS
        else:
            fix_quality = 0  # No fix
        
        # Calculate dilution of precision (simplified)
        if num_sats >= 4:
            hdop = max(0.8, 5.0 / num_sats + random.uniform(-0.2, 0.2))
            vdop = hdop * 1.2
            pdop = math.sqrt(hdop**2 + vdop**2)
        else:
            hdop = vdop = pdop = 99.9
        
        # Add position noise based on conditions
        pos_noise = 0.0
        if vehicle_state.jamming_level > 50:
            pos_noise = random.uniform(-0.001, 0.001)  # ~100m noise
        elif vehicle_state.jamming_level > 20:
            pos_noise = random.uniform(-0.0001, 0.0001)  # ~10m noise
        else:
            pos_noise = random.uniform(-0.00001, 0.00001)  # ~1m noise
        
        try:
            # Create sentences manually to avoid parameter issues
            
            # GGA - Global Positioning System Fix Data
            lat_deg = abs(vehicle_state.latitude + pos_noise)
            lon_deg = abs(vehicle_state.longitude + pos_noise)
            lat_dir = 'N' if vehicle_state.latitude >= 0 else 'S'
            lon_dir = 'E' if vehicle_state.longitude >= 0 else 'W'
            
            # Convert to DDMM.MMMMM format
            lat_dd = int(lat_deg)
            lat_mm = (lat_deg - lat_dd) * 60
            lat_str = f"{lat_dd:02d}{lat_mm:07.4f}"
            
            lon_dd = int(lon_deg)
            lon_mm = (lon_deg - lon_dd) * 60
            lon_str = f"{lon_dd:03d}{lon_mm:07.4f}"
            
            gga_sentence = (f"$GPGGA,{time_str},{lat_str},{lat_dir},{lon_str},{lon_dir},"
                           f"{fix_quality},{num_sats:02d},{hdop:.1f},{vehicle_state.altitude:.1f},M,0.0,M,,")
            
            # Calculate checksum
            checksum = 0
            for char in gga_sentence[1:]:  # Skip the $
                checksum ^= ord(char)
            gga_sentence += f"*{checksum:02X}"
            
            sentences.append(gga_sentence)
            
            # RMC - Recommended Minimum Navigation Information
            status = 'A' if fix_quality > 0 else 'V'
            speed_knots = vehicle_state.speed * 1.94384  # m/s to knots
            
            rmc_sentence = (f"$GPRMC,{time_str},{status},{lat_str},{lat_dir},{lon_str},{lon_dir},"
                           f"{speed_knots:.1f},{vehicle_state.heading:.1f},{date_str},,")
            
            # Calculate checksum
            checksum = 0
            for char in rmc_sentence[1:]:
                checksum ^= ord(char)
            rmc_sentence += f"*{checksum:02X}"
            
            sentences.append(rmc_sentence)
            
            # GSA - GPS DOP and Active Satellites
            mode_fix = min(3, max(1, len(solution_sats)))
            sat_ids = [str(sat.prn) for sat in solution_sats[:12]]
            while len(sat_ids) < 12:
                sat_ids.append("")
            
            gsa_sentence = f"$GPGSA,A,{mode_fix}," + ",".join(sat_ids) + f",{pdop:.1f},{hdop:.1f},{vdop:.1f}"
            
            # Calculate checksum
            checksum = 0
            for char in gsa_sentence[1:]:
                checksum ^= ord(char)
            gsa_sentence += f"*{checksum:02X}"
            
            sentences.append(gsa_sentence)
            
            # GSV - GPS Satellites in View
            all_visible = visible_sats[:16]  # Limit to 16 satellites
            num_sentences = (len(all_visible) + 3) // 4  # 4 satellites per sentence
            
            for sentence_num in range(num_sentences):
                start_idx = sentence_num * 4
                end_idx = min(start_idx + 4, len(all_visible))
                sentence_sats = all_visible[start_idx:end_idx]
                
                gsv_sentence = f"$GPGSV,{num_sentences},{sentence_num + 1},{len(all_visible)}"
                
                for sat in sentence_sats:
                    gsv_sentence += f",{sat.prn:02d},{int(sat.elevation):02d},{int(sat.azimuth):03d},{int(sat.snr):02d}"
                
                # Pad with empty fields if needed
                for _ in range(len(sentence_sats), 4):
                    gsv_sentence += ",,,,"
                
                # Calculate checksum
                checksum = 0
                for char in gsv_sentence[1:]:
                    checksum ^= ord(char)
                gsv_sentence += f"*{checksum:02X}"
                
                sentences.append(gsv_sentence)
            
        except Exception as e:
            print(f"Error generating NMEA sentences: {e}")
            # Return minimal sentences on error
            sentences = [
                "$GPGGA,000000.00,0000.0000,N,00000.0000,W,0,00,99.9,0.0,M,0.0,M,,*65",
                "$GPRMC,000000.00,V,0000.0000,N,00000.0000,W,0.0,0.0,010100,,*7C"
            ]
        
        return sentences
    
    def generate_rtcm_messages(self, vehicle_state: VehicleState) -> List[bytes]:
        """Generate simple RTCM messages for RTK corrections."""
        messages = []
        
        try:
            # Create a basic RTCM 1005 message (simplified)
            # This is just a placeholder - real RTCM is much more complex
            msg_data = b'\x00' * 20  # 20 bytes of placeholder data
            
            # RTCM frame: preamble (0xD3) + reserved + length + message type + data + CRC
            preamble = 0xD3
            reserved = 0x00
            length = len(msg_data)
            msg_type = 1005
            
            # Pack header properly - ensure all values are in byte range
            header_byte1 = preamble & 0xFF
            header_byte2 = reserved & 0xFF
            
            # Pack length and message type into 2 bytes
            # Length is 10 bits, message type is 12 bits, but we need to fit in bytes
            length_bits = (length & 0x3FF) << 6  # 10 bits for length
            msg_type_high = (msg_type >> 4) & 0x3F  # Upper 6 bits of message type
            header_byte3 = (length_bits >> 8) | msg_type_high
            header_byte3 = header_byte3 & 0xFF
            
            msg_type_low = (msg_type & 0x0F) << 4  # Lower 4 bits of message type
            header_byte4 = msg_type_low & 0xFF
            
            # Build header
            header = bytes([header_byte1, header_byte2, header_byte3, header_byte4])
            
            # Build complete message
            full_msg = header + msg_data
            
            # Simple CRC calculation (not real CRC24Q, just for demo)
            crc_value = 0
            for byte in full_msg:
                crc_value = (crc_value + byte) & 0xFFFFFF
            
            # Convert CRC to 3 bytes
            crc_byte1 = (crc_value >> 16) & 0xFF
            crc_byte2 = (crc_value >> 8) & 0xFF
            crc_byte3 = crc_value & 0xFF
            crc_bytes = bytes([crc_byte1, crc_byte2, crc_byte3])
            
            # Complete message
            complete_msg = full_msg + crc_bytes
            messages.append(complete_msg)
            
        except Exception as e:
            print(f"Error generating RTCM messages: {e}")
            # Return empty list on error rather than crashing
            return []
        
        return messages
    
    def handle_vehicle_request(self, vehicle_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request from a vehicle for GPS data."""
        # Update or create vehicle state
        if vehicle_id not in self.vehicle_states:
            self.vehicle_states[vehicle_id] = VehicleState(
                vehicle_id=vehicle_id,
                latitude=request_data.get('latitude', 40.7128),
                longitude=request_data.get('longitude', -74.0060),
                altitude=request_data.get('altitude', 10.0),
                speed=request_data.get('speed', 0.0),
                heading=request_data.get('heading', 0.0),
                last_request_time=time.time()
            )
        else:
            # Update existing state
            state = self.vehicle_states[vehicle_id]
            state.latitude = request_data.get('latitude', state.latitude)
            state.longitude = request_data.get('longitude', state.longitude)
            state.altitude = request_data.get('altitude', state.altitude)
            state.speed = request_data.get('speed', state.speed)
            state.heading = request_data.get('heading', state.heading)
            state.last_request_time = time.time()
        
        vehicle_state = self.vehicle_states[vehicle_id]
        
        # Update environmental conditions
        vehicle_state.gps_denied = request_data.get('gps_denied', False)
        vehicle_state.jamming_level = request_data.get('jamming_level', 0.0)
        vehicle_state.environmental_factor = request_data.get('environmental_factor', 1.0)
        
        # Generate NMEA sentences
        nmea_sentences = self.generate_nmea_sentences(vehicle_state)
        
        # Generate RTCM messages
        rtcm_messages = self.generate_rtcm_messages(vehicle_state)
        
        response = {
            'vehicle_id': vehicle_id,
            'timestamp': time.time(),
            'nmea_sentences': nmea_sentences,
            'rtcm_messages': [msg.hex() for msg in rtcm_messages],
            'satellite_count': len(self.get_visible_satellites(vehicle_state)),
            'fix_quality': self._get_fix_quality(vehicle_state),
            'signal_quality': self._get_average_signal_quality(vehicle_state)
        }
        
        return response
    
    def _get_fix_quality(self, vehicle_state: VehicleState) -> int:
        """Get current fix quality for a vehicle."""
        visible_sats = self.get_visible_satellites(vehicle_state)
        num_sats = len(visible_sats)
        
        if vehicle_state.gps_denied or num_sats == 0:
            return 0  # No fix
        elif num_sats >= 6:
            return 6  # RTK fixed
        elif num_sats >= 4:
            return 4  # DGPS
        else:
            return 1  # GPS SPS
    
    def _get_average_signal_quality(self, vehicle_state: VehicleState) -> float:
        """Get average signal quality for a vehicle."""
        visible_sats = self.get_visible_satellites(vehicle_state)
        if not visible_sats:
            return 0.0
        
        return sum(sat.snr for sat in visible_sats) / len(visible_sats)
    
    def start_server(self):
        """Start the TCP server to handle vehicle requests."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        host = self.config["server"]["host"]
        port = self.config["server"]["port"]
        
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        
        self.running = True
        print(f"Satellite Constellation Server listening on {host}:{port}")
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"Connection from {address}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
                
            except socket.error as e:
                if self.running:
                    print(f"Server error: {e}")
                break
    
    def handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle individual client connections."""
        try:
            while self.running:
                # Receive request
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    request = json.loads(data.decode('utf-8'))
                    vehicle_id = request.get('vehicle_id', f'unknown_{address[0]}_{address[1]}')
                    
                    # Process request
                    response = self.handle_vehicle_request(vehicle_id, request)
                    
                    # Send response
                    response_data = json.dumps(response).encode('utf-8')
                    client_socket.send(response_data)
                    
                except json.JSONDecodeError:
                    error_response = {'error': 'Invalid JSON request'}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                except Exception as e:
                    error_response = {'error': f'Server error: {str(e)}'}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                
                time.sleep(0.1)  # Prevent busy loop
                
        except Exception as e:
            print(f"Client handler error: {e}")
        finally:
            client_socket.close()
            print(f"Closed connection to {address}")
    
    def stop_server(self):
        """Stop the server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Satellite Constellation Server stopped")


def main():
    """Main function to run the satellite constellation simulator."""
    print("Satellite Constellation Simulator")
    print("=================================")
    
    # Create constellation
    constellation = SatelliteConstellation()
    
    try:
        # Start server
        constellation.start_server()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        constellation.stop_server()


if __name__ == "__main__":
    main()