#!/usr/bin/env python3
"""
Satellite Orbital Model
Manages GPS satellite positions and orbital mechanics for visualization
"""
import random
import math
import time
from typing import List, Tuple, Dict
from dataclasses import dataclass

@dataclass
class Satellite:
    """Represents a single GPS satellite"""
    prn: int  # Pseudo-Random Number (satellite ID)
    angle: float  # Current angle in radians (0 to 2π)
    angular_velocity: float  # Radians per second (positive=counterclockwise, negative=clockwise)
    orbit_radius: float  # Distance from origin
    constellation: str  # GPS, GLONASS, or Galileo
    
    def update_position(self, delta_time: float):
        """Update satellite position based on time elapsed"""
        self.angle += self.angular_velocity * delta_time
        # Normalize angle to [0, 2π)
        self.angle = self.angle % (2 * math.pi)
    
    def get_position(self) -> Tuple[float, float]:
        """Get current (x, y) position"""
        x = self.orbit_radius * math.cos(self.angle)
        y = self.orbit_radius * math.sin(self.angle)
        return (x, y)
    
    def get_latlon(self, base_lat: float = 0.0, base_lon: float = 0.0) -> Tuple[float, float]:
        """Convert orbital position to approximate lat/lon for GPS purposes"""
        x, y = self.get_position()
        # Simple conversion: scale orbital coordinates to lat/lon offsets
        # This is approximate - real GPS satellites are in 3D space
        lat_offset = y * 0.1  # Scale factor
        lon_offset = x * 0.1
        return (base_lat + lat_offset, base_lon + lon_offset)


class SatelliteConstellation:
    """Manages the complete satellite constellation"""
    
    def __init__(self, 
                 num_gps: int = 24,
                 num_glonass: int = 24,
                 num_galileo: int = 30,
                 orbit_radius: float = 8.0,
                 min_angular_velocity: float = 0.05,
                 max_angular_velocity: float = 0.15):
        """
        Initialize satellite constellation
        
        Args:
            num_gps: Number of GPS satellites
            num_glonass: Number of GLONASS satellites
            num_galileo: Number of Galileo satellites
            orbit_radius: Orbital radius in simulation units
            min_angular_velocity: Minimum orbital speed (rad/s)
            max_angular_velocity: Maximum orbital speed (rad/s)
        """
        self.orbit_radius = orbit_radius
        self.satellites: List[Satellite] = []
        self.last_update_time = time.time()
        
        # Create GPS satellites
        for i in range(num_gps):
            prn = i + 1
            angle = random.uniform(0, 2 * math.pi)
            # Randomly choose clockwise (negative) or counterclockwise (positive)
            direction = random.choice([-1, 1])
            velocity = direction * random.uniform(min_angular_velocity, max_angular_velocity)
            
            self.satellites.append(Satellite(
                prn=prn,
                angle=angle,
                angular_velocity=velocity,
                orbit_radius=orbit_radius,
                constellation="GPS"
            ))
        
        # Create GLONASS satellites
        for i in range(num_glonass):
            prn = i + 1
            angle = random.uniform(0, 2 * math.pi)
            direction = random.choice([-1, 1])
            velocity = direction * random.uniform(min_angular_velocity, max_angular_velocity)
            
            self.satellites.append(Satellite(
                prn=prn + 100,  # Offset PRN to avoid conflicts
                angle=angle,
                angular_velocity=velocity,
                orbit_radius=orbit_radius,
                constellation="GLONASS"
            ))
        
        # Create Galileo satellites
        for i in range(num_galileo):
            prn = i + 1
            angle = random.uniform(0, 2 * math.pi)
            direction = random.choice([-1, 1])
            velocity = direction * random.uniform(min_angular_velocity, max_angular_velocity)
            
            self.satellites.append(Satellite(
                prn=prn + 200,  # Offset PRN to avoid conflicts
                angle=angle,
                angular_velocity=velocity,
                orbit_radius=orbit_radius,
                constellation="Galileo"
            ))
        
        print(f"[SATELLITES] Initialized constellation:")
        print(f"  GPS: {num_gps} satellites")
        print(f"  GLONASS: {num_glonass} satellites")
        print(f"  Galileo: {num_galileo} satellites")
        print(f"  Total: {len(self.satellites)} satellites")
        print(f"  Orbit radius: {orbit_radius} units")
    
    def update(self):
        """Update all satellite positions based on elapsed time"""
        current_time = time.time()
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time
        
        for satellite in self.satellites:
            satellite.update_position(delta_time)
    
    def get_all_positions(self) -> Dict[str, List[Tuple[float, float]]]:
        """Get positions of all satellites grouped by constellation"""
        positions = {
            "GPS": [],
            "GLONASS": [],
            "Galileo": []
        }
        
        for sat in self.satellites:
            pos = sat.get_position()
            positions[sat.constellation].append(pos)
        
        return positions
    
    def get_satellites_by_constellation(self, constellation: str) -> List[Satellite]:
        """Get all satellites from a specific constellation"""
        return [sat for sat in self.satellites if sat.constellation == constellation]
    
    def get_visible_satellites(self, agent_position: Tuple[float, float], 
                              max_distance: float = 15.0) -> List[Satellite]:
        """
        Get satellites visible from an agent's position
        
        Args:
            agent_position: Agent's (x, y) position
            max_distance: Maximum visibility distance
            
        Returns:
            List of visible satellites
        """
        visible = []
        agent_x, agent_y = agent_position
        
        for sat in self.satellites:
            sat_x, sat_y = sat.get_position()
            distance = math.sqrt((sat_x - agent_x)**2 + (sat_y - agent_y)**2)
            
            if distance <= max_distance:
                visible.append(sat)
        
        return visible
    
    def get_satellite_info(self) -> List[Dict]:
        """Get detailed information about all satellites"""
        info = []
        for sat in self.satellites:
            x, y = sat.get_position()
            direction = "Counterclockwise" if sat.angular_velocity > 0 else "Clockwise"
            
            info.append({
                "prn": sat.prn,
                "constellation": sat.constellation,
                "position": (x, y),
                "angle_deg": math.degrees(sat.angle),
                "direction": direction,
                "angular_velocity": sat.angular_velocity
            })
        
        return info
    
    def get_orbit_circle_points(self, num_points: int = 100) -> List[Tuple[float, float]]:
        """Get points defining the orbital circle for plotting"""
        points = []
        for i in range(num_points + 1):
            angle = (2 * math.pi * i) / num_points
            x = self.orbit_radius * math.cos(angle)
            y = self.orbit_radius * math.sin(angle)
            points.append((x, y))
        return points


# Factory function for easy integration
def create_satellite_constellation(config: dict = None) -> SatelliteConstellation:
    """
    Create satellite constellation with configuration
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        SatelliteConstellation instance
    """
    if config is None:
        config = {}
    
    return SatelliteConstellation(
        num_gps=config.get('gps_satellites', 24),
        num_glonass=config.get('glonass_satellites', 24),
        num_galileo=config.get('galileo_satellites', 30),
        orbit_radius=config.get('orbit_radius', 8.0),
        min_angular_velocity=config.get('min_angular_velocity', 0.05),
        max_angular_velocity=config.get('max_angular_velocity', 0.15)
    )


if __name__ == "__main__":
    # Test the satellite constellation
    print("Testing Satellite Orbital Model")
    print("=" * 60)
    
    constellation = SatelliteConstellation(
        num_gps=12,
        num_glonass=8,
        num_galileo=10,
        orbit_radius=8.0
    )
    
    print("\nInitial satellite positions:")
    for i, sat in enumerate(constellation.satellites[:5]):
        x, y = sat.get_position()
        print(f"  Sat {sat.prn} ({sat.constellation}): ({x:.2f}, {y:.2f})")
    
    print("\nSimulating 5 seconds of orbital motion...")
    for _ in range(5):
        time.sleep(1)
        constellation.update()
    
    print("\nFinal satellite positions:")
    for i, sat in enumerate(constellation.satellites[:5]):
        x, y = sat.get_position()
        print(f"  Sat {sat.prn} ({sat.constellation}): ({x:.2f}, {y:.2f})")
    
    print("\nOrbit circle points:", len(constellation.get_orbit_circle_points()))
    print("\nTest complete!")