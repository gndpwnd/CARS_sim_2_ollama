#!/usr/bin/env python3
"""
Simplified GPS NMEA Generator - NMEA messages only
Simulates signal degradation in jamming zones
"""

import json
import math
import random
import socket
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SatelliteInfo:
    prn: int
    elevation: float
    azimuth: float
    snr: float


class SimpleGPSConstellation:
    """Simplified GPS constellation - NMEA only"""
    
    def __init__(self, host="0.0.0.0", port=12345):
        self.host = host
        self.port = port
        self.running = False
        
        # Generate 12-24 satellites
        self.satellites = self._generate_satellites()
        
    def _generate_satellites(self) -> List[SatelliteInfo]:
        """Generate satellite constellation"""
        satellites = []
        for prn in range(1, 25):  # 24 satellites
            satellites.append(SatelliteInfo(
                prn=prn,
                elevation=random.uniform(15, 85),
                azimuth=random.uniform(0, 360),
                snr=random.uniform(35, 50)
            ))
        return satellites
    
    def calculate_jamming_effect(self, jamming_level: float) -> dict:
        """Calculate GPS degradation from jamming"""
        if jamming_level == 0:
            return {
                'satellite_count': random.randint(8, 12),
                'fix_quality': 6,  # RTK fixed
                'avg_snr': random.uniform(42, 48),
                'hdop': random.uniform(0.8, 1.2)
            }
        elif jamming_level < 30:
            return {
                'satellite_count': random.randint(6, 8),
                'fix_quality': 4,  # DGPS
                'avg_snr': random.uniform(35, 42),
                'hdop': random.uniform(1.2, 2.5)
            }
        elif jamming_level < 70:
            return {
                'satellite_count': random.randint(3, 5),
                'fix_quality': 1,  # GPS fix
                'avg_snr': random.uniform(25, 35),
                'hdop': random.uniform(2.5, 5.0)
            }
        else:
            return {
                'satellite_count': 0,
                'fix_quality': 0,  # No fix
                'avg_snr': 0,
                'hdop': 99.9
            }
    
    def generate_nmea_gga(self, lat: float, lon: float, alt: float, 
                         metrics: dict, utc_time: str) -> str:
        """Generate GGA sentence"""
        # Convert to DDMM.MMMM format
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if lat >= 0 else 'S'
        
        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if lon >= 0 else 'W'
        
        sentence = (
            f"$GPGGA,{utc_time},{lat_str},{lat_dir},{lon_str},{lon_dir},"
            f"{metrics['fix_quality']},{metrics['satellite_count']:02d},"
            f"{metrics['hdop']:.1f},{alt:.1f},M,0.0,M,,"
        )
        
        # Calculate checksum
        checksum = 0
        for char in sentence[1:]:
            checksum ^= ord(char)
        
        return f"{sentence}*{checksum:02X}"
    
    def generate_nmea_rmc(self, lat: float, lon: float, speed: float,
                         heading: float, utc_time: str, date_str: str,
                         has_fix: bool) -> str:
        """Generate RMC sentence"""
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = 'N' if lat >= 0 else 'S'
        
        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = 'E' if lon >= 0 else 'W'
        
        status = 'A' if has_fix else 'V'
        speed_knots = speed * 1.94384  # m/s to knots
        
        sentence = (
            f"$GPRMC,{utc_time},{status},{lat_str},{lat_dir},{lon_str},{lon_dir},"
            f"{speed_knots:.1f},{heading:.1f},{date_str},,"
        )
        
        checksum = 0
        for char in sentence[1:]:
            checksum ^= ord(char)
        
        return f"{sentence}*{checksum:02X}"
    
    def generate_nmea_gsv(self, visible_sats: List[SatelliteInfo]) -> List[str]:
        """Generate GSV sentences (satellite info)"""
        sentences = []
        num_sentences = (len(visible_sats) + 3) // 4
        
        for i in range(num_sentences):
            start_idx = i * 4
            end_idx = min(start_idx + 4, len(visible_sats))
            sats = visible_sats[start_idx:end_idx]
            
            sentence = f"$GPGSV,{num_sentences},{i+1},{len(visible_sats)}"
            
            for sat in sats:
                sentence += f",{sat.prn:02d},{int(sat.elevation):02d},"
                sentence += f"{int(sat.azimuth):03d},{int(sat.snr):02d}"
            
            # Pad if needed
            for _ in range(len(sats), 4):
                sentence += ",,,,"
            
            checksum = 0
            for char in sentence[1:]:
                checksum ^= ord(char)
            
            sentences.append(f"{sentence}*{checksum:02X}")
        
        return sentences
    
    def handle_request(self, request: dict) -> dict:
        """Handle GPS data request"""
        vehicle_id = request.get('vehicle_id', 'unknown')
        latitude = request.get('latitude', 0)
        longitude = request.get('longitude', 0)
        altitude = request.get('altitude', 0)
        speed = request.get('speed', 0)
        heading = request.get('heading', 0)
        jamming_level = request.get('jamming_level', 0)
        
        # Calculate GPS metrics based on jamming
        metrics = self.calculate_jamming_effect(jamming_level)
        
        # Generate timestamp
        utc_now = datetime.now(timezone.utc)
        time_str = utc_now.strftime("%H%M%S.%f")[:-3]
        date_str = utc_now.strftime("%d%m%y")
        
        # Select visible satellites
        num_visible = metrics['satellite_count']
        visible_sats = sorted(self.satellites, key=lambda s: s.snr, reverse=True)[:num_visible]
        
        # Apply jamming to SNR
        for sat in visible_sats:
            sat.snr = max(20, sat.snr * (1 - jamming_level/100))
        
        # Generate NMEA sentences
        nmea_sentences = []
        
        # GGA - Position
        nmea_sentences.append(self.generate_nmea_gga(
            latitude, longitude, altitude, metrics, time_str
        ))
        
        # RMC - Navigation
        nmea_sentences.append(self.generate_nmea_rmc(
            latitude, longitude, speed, heading, time_str, date_str,
            metrics['fix_quality'] > 0
        ))
        
        # GSV - Satellites in view
        if num_visible > 0:
            nmea_sentences.extend(self.generate_nmea_gsv(visible_sats))
        
        return {
            'vehicle_id': vehicle_id,
            'timestamp': time.time(),
            'nmea_sentences': nmea_sentences,
            'rtcm_messages': [],  # Empty but present
            'satellite_count': metrics['satellite_count'],
            'fix_quality': metrics['fix_quality'],
            'signal_quality': metrics['avg_snr']
        }
    
    def start_server(self):
        """Start TCP server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        self.running = True
        print(f"[GPS] Server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                data = client_socket.recv(4096)
                
                if data:
                    request = json.loads(data.decode('utf-8'))
                    response = self.handle_request(request)
                    client_socket.send(json.dumps(response).encode('utf-8'))
                
                client_socket.close()
                
            except Exception as e:
                if self.running:
                    print(f"[GPS] Error: {e}")
        
        server_socket.close()


if __name__ == "__main__":
    gps = SimpleGPSConstellation()
    gps.start_server()