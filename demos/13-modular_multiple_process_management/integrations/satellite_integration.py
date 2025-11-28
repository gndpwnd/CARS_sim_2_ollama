#!/usr/bin/env python3
"""
Satellite Integration Module
Connects satellite constellation with GUI and simulation
"""
import json
from typing import Optional, Dict, Any
from satellite_orbital_model import SatelliteConstellation, create_satellite_constellation


def load_satellite_config(config_file: str = "constellation_config.json") -> Dict[str, Any]:
    """
    Load satellite configuration from file
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"[SAT] Loaded configuration from {config_file}")
        return config
    except FileNotFoundError:
        print(f"[SAT] Config file not found, using defaults")
        return {}
    except Exception as e:
        print(f"[SAT] Error loading config: {e}")
        return {}


def initialize_satellites(config_file: str = "constellation_config.json",
                         orbit_radius: float = 8.0) -> Optional[SatelliteConstellation]:
    """
    Initialize satellite constellation for simulation
    
    Args:
        config_file: Path to configuration file
        orbit_radius: Orbital radius in simulation units
        
    Returns:
        SatelliteConstellation instance or None on failure
    """
    try:
        # Load configuration
        config = load_satellite_config(config_file)
        
        # Override orbit radius if specified
        if orbit_radius != 8.0:
            config['orbit_radius'] = orbit_radius
        elif 'orbit_radius' not in config:
            config['orbit_radius'] = 8.0
        
        # Create constellation
        constellation = create_satellite_constellation(config)
        
        print(f"[SAT] Satellite constellation initialized successfully")
        print(f"[SAT] Total satellites: {len(constellation.satellites)}")
        print(f"[SAT] Orbit radius: {constellation.orbit_radius} units")
        
        return constellation
        
    except Exception as e:
        print(f"[SAT] Failed to initialize satellites: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_constellation(constellation: Optional[SatelliteConstellation]) -> bool:
    """
    Update satellite positions
    
    Args:
        constellation: Satellite constellation to update
        
    Returns:
        True if successful, False otherwise
    """
    if constellation is None:
        return False
    
    try:
        constellation.update()
        return True
    except Exception as e:
        print(f"[SAT] Error updating constellation: {e}")
        return False


def get_visible_satellites_for_agent(constellation: Optional[SatelliteConstellation],
                                    agent_position: tuple,
                                    max_distance: float = 15.0) -> list:
    """
    Get satellites visible from an agent's position
    
    Args:
        constellation: Satellite constellation
        agent_position: Agent (x, y) position
        max_distance: Maximum visibility distance
        
    Returns:
        List of visible satellites
    """
    if constellation is None:
        return []
    
    try:
        return constellation.get_visible_satellites(agent_position, max_distance)
    except Exception as e:
        print(f"[SAT] Error getting visible satellites: {e}")
        return []


def calculate_satellite_metrics(constellation: Optional[SatelliteConstellation],
                                agent_position: tuple) -> Dict[str, Any]:
    """
    Calculate GPS metrics based on visible satellites
    
    Args:
        constellation: Satellite constellation
        agent_position: Agent position
        
    Returns:
        Dictionary with GPS metrics
    """
    if constellation is None:
        return {
            'visible_satellites': 0,
            'gps_available': False,
            'estimated_accuracy': 99.9
        }
    
    try:
        visible = constellation.get_visible_satellites(agent_position)
        
        # Calculate metrics
        num_visible = len(visible)
        gps_available = num_visible >= 4  # Need at least 4 for position fix
        
        # Estimate accuracy based on number of satellites
        if num_visible == 0:
            accuracy = 99.9
        elif num_visible < 4:
            accuracy = 10.0
        elif num_visible < 6:
            accuracy = 5.0
        elif num_visible < 8:
            accuracy = 2.5
        else:
            accuracy = 1.0
        
        # Count by constellation
        constellation_counts = {}
        for sat in visible:
            constellation_counts[sat.constellation] = \
                constellation_counts.get(sat.constellation, 0) + 1
        
        return {
            'visible_satellites': num_visible,
            'gps_available': gps_available,
            'estimated_accuracy': accuracy,
            'constellation_counts': constellation_counts,
            'satellite_list': [
                {
                    'prn': sat.prn,
                    'constellation': sat.constellation,
                    'position': sat.get_position()
                }
                for sat in visible
            ]
        }
        
    except Exception as e:
        print(f"[SAT] Error calculating metrics: {e}")
        return {
            'visible_satellites': 0,
            'gps_available': False,
            'estimated_accuracy': 99.9,
            'error': str(e)
        }


def format_satellite_status(constellation: Optional[SatelliteConstellation]) -> str:
    """
    Format satellite constellation status for display
    
    Args:
        constellation: Satellite constellation
        
    Returns:
        Formatted status string
    """
    if constellation is None:
        return "Satellite constellation: OFFLINE"
    
    try:
        info = constellation.get_satellite_info()
        
        # Count by constellation
        counts = {}
        for sat_info in info:
            const = sat_info['constellation']
            counts[const] = counts.get(const, 0) + 1
        
        status = "Satellite Constellation Status:\n"
        status += f"  Total: {len(info)} satellites\n"
        for const_name, count in counts.items():
            status += f"  {const_name}: {count} satellites\n"
        status += f"  Orbit radius: {constellation.orbit_radius} units\n"
        
        return status
        
    except Exception as e:
        return f"Satellite constellation: ERROR ({e})"


# Export main functions
__all__ = [
    'initialize_satellites',
    'update_constellation',
    'get_visible_satellites_for_agent',
    'calculate_satellite_metrics',
    'format_satellite_status',
    'load_satellite_config'
]