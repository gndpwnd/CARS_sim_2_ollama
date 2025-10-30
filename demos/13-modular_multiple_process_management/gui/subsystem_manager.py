"""
Unified Subsystem Manager for GPS Simulation GUI
Handles GPS, Requirements Monitoring, and Telemetry with proper integration
"""
from typing import Optional, Dict, Any, List, Tuple
import threading
import traceback
from datetime import datetime

# Core configuration
from core.config import (
    GPS_BASE_LATITUDE, GPS_BASE_LONGITUDE,
    GPS_CONSTELLATION_HOST, GPS_CONSTELLATION_PORT,
    DEFAULT_JAMMING_CENTER, DEFAULT_JAMMING_RADIUS
)

# GPS integration
from gps_client_lib import AgentGPSManager, parse_nmea_gga, GPSFix, SatelliteInfo
from vehicle_requirements_tracker import VehicleRequirementsTracker
from integrations import log_event

# Jamming calculations
from simulation.sim_jamming import calculate_jamming_level

# Storage systems
try:
    from qdrant_store import add_telemetry, add_nmea_message
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[SUBSYSTEMS] Qdrant not available")

class SubsystemManager:
    """
    Unified manager for all simulation subsystems:
    - GPS integration and data processing
    - Requirements monitoring and verification
    - Telemetry logging and storage
    - Jamming simulation and monitoring
    """
    
    def __init__(self, gui):
        """
        Initialize subsystem manager
        
        Args:
            gui: Parent GUI window for accessing simulation state
        """
        self.gui = gui
        
        # Core components
        self.gps_manager = None
        self.requirements_monitor = None
        
        # State tracking
        self.gps_data_cache = {}  # Cache recent GPS data
        self.last_telemetry_update = {}  # Rate limiting
        self.agent_states = {}  # Track agent status
        
        # Thread safety
        self.telemetry_lock = threading.Lock()
        self.gps_lock = threading.Lock()
        
        # Storage system status
        self.qdrant_ready = QDRANT_AVAILABLE
    
    def initialize_all(self):
        """Initialize all subsystems with proper error handling"""
        success = True
        
        # Initialize in order of dependency
        if not self.initialize_gps():
            print("[SUBSYSTEMS] ⚠️ GPS initialization failed")
            success = False
        
        if not self.initialize_requirements_monitor():
            print("[SUBSYSTEMS] ⚠️ Requirements monitoring failed")
            success = False
        
        return success
    
    def initialize_gps(self) -> bool:
        """
        Initialize GPS subsystem with connection verification
        
        Returns:
            bool: True if initialization successful
        """
        try:
            print("[GPS] Initializing GPS manager...")
            self.gps_manager = AgentGPSManager(
                constellation_host=GPS_CONSTELLATION_HOST,
                constellation_port=GPS_CONSTELLATION_PORT,
                base_latitude=GPS_BASE_LATITUDE,
                base_longitude=GPS_BASE_LONGITUDE
            )
            
            # Start the GPS manager
            self.gps_manager.start()
            print("[GPS] ✓ GPS manager initialized and started")
            return True
                
        except Exception as e:
            print(f"[GPS] ✗ Error initializing GPS: {e}")
            traceback.print_exc()
            self.gps_manager = None
            return False
    
    def initialize_requirements_monitor(self) -> bool:
        """
        Initialize requirements monitoring system
        
        Returns:
            bool: True if initialization successful
        """
        try:
            print("[REQ] Initializing requirements monitor...")
            self.requirements_monitor = VehicleRequirementsTracker()
            
            # Load initial configuration
            if self.requirements_monitor.load_requirements_config():
                print("[REQ] ✓ Requirements monitor initialized")
                return True
            else:
                print("[REQ] ✗ Failed to load requirements configuration")
                self.requirements_monitor = None
                return False
                
        except Exception as e:
            print(f"[REQ] ✗ Error initializing requirements: {e}")
            traceback.print_exc()
            self.requirements_monitor = None
            return False
    
    def update_agent_gps(self, agent_id: str, position: tuple, is_jammed: bool):
        """
        Comprehensive agent update including GPS, requirements, and telemetry
        
        Args:
            agent_id: Agent identifier
            position: (x, y) coordinates
            is_jammed: Whether agent is in jamming zone
        """
        if not self.gps_manager:
            return
        
        try:
            with self.gps_lock:
                # Calculate actual jamming effect
                jamming_level = calculate_jamming_level(position, self.gui.jamming_zones)
                
                # Update GPS with jamming information
                gps_data = self.gps_manager.update_agent_gps(
                    agent_id=agent_id,
                    position=position,
                    jamming_center=DEFAULT_JAMMING_CENTER,
                    jamming_radius=DEFAULT_JAMMING_RADIUS,
                    gps_denied=is_jammed or jamming_level > 90
                )
                
                if not gps_data:
                    return
                
                # Cache GPS data
                self.gps_data_cache[agent_id] = gps_data
                
                # Update requirements monitor
                if self.requirements_monitor:
                    self._update_requirements(
                        agent_id, 
                        gps_data, 
                        position, 
                        is_jammed,
                        jamming_level
                    )
                
                # Log telemetry and events
                self._log_telemetry(agent_id, position, is_jammed, gps_data)
                self._log_gps_metrics(agent_id, gps_data, position)
                
                # Parse GGA data for agent state
                gga_data = None
                for sentence in gps_data.nmea_sentences:
                    if 'GGA' in sentence:
                        gga_data = parse_nmea_gga(sentence)
                        break
                
                fix_quality = gga_data.get('fix_quality', 0) if gga_data and gga_data.get('valid') else 0
                satellite_count = gga_data.get('satellites', 0) if gga_data and gga_data.get('valid') else 0
                
                # Update agent state
                self.agent_states[agent_id] = {
                    'position': position,
                    'jammed': is_jammed or jamming_level > 90,
                    'jamming_level': jamming_level,
                    'gps_quality': fix_quality,
                    'satellites': satellite_count,
                    'hdop': gga_data.get('hdop', 99.9) if gga_data and gga_data.get('valid') else 99.9,
                    'last_update': datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"[GPS] Error updating agent {agent_id}: {e}")
            traceback.print_exc()
    
    def _log_telemetry(self, agent_id: str, position: tuple, is_jammed: bool, gps_data: Any):
        """
        Log telemetry data to Qdrant with rate limiting
        
        Args:
            agent_id: Agent identifier
            position: Current position
            is_jammed: Jamming status
            gps_data: GPS data object
        """
        if not self.qdrant_ready:
            return
            
        with self.telemetry_lock:
            current_time = datetime.now().timestamp()
            last_update = self.last_telemetry_update.get(agent_id, 0)
            
            # Rate limit to max 1 update per second per agent
            if current_time - last_update >= 1.0:
                try:
                    jamming_level = calculate_jamming_level(position, self.gui.jamming_zones)
                    
                    # Parse GGA data for metadata
                    gga_info = None
                    for sentence in gps_data.nmea_sentences:
                        if 'GGA' in sentence:
                            gga_info = parse_nmea_gga(sentence)
                            break
                    
                    # Build rich telemetry metadata
                    metadata = {
                        'jammed': is_jammed,
                        'jamming_level': jamming_level,
                        'communication_quality': max(0.2, 1.0 - (jamming_level / 100)),
                        'timestamp': datetime.now().isoformat(),
                        'iteration': self.gui.iteration_count,
                        'gps_satellites': gga_info['satellites'] if gga_info and gga_info.get('valid') else 0,
                        'gps_fix_quality': gga_info['fix_quality'] if gga_info and gga_info.get('valid') else 0,
                        'hdop': gga_info['hdop'] if gga_info and gga_info.get('valid') else 99.9
                    }
                    
                    # Add position telemetry
                    add_telemetry(agent_id, position, metadata)
                    
                    # Add NMEA messages if significant
                    for sentence in gps_data.nmea_sentences:
                        if 'GGA' in sentence:  # Only log GGA messages
                            gga_info = parse_nmea_gga(sentence)
                            if gga_info.get('valid') and gga_info.get('fix_quality', 0) > 0:
                                add_nmea_message(
                                    agent_id,
                                    sentence,
                                    {
                                        'position': position,
                                        'fix_quality': gga_info['fix_quality'],
                                        'satellites': gga_info['satellites'],
                                        'jammed': is_jammed,
                                        'jamming_level': jamming_level
                                    }
                                )
                    
                    self.last_telemetry_update[agent_id] = current_time
                    
                except Exception as e:
                    print(f"[TELEMETRY] Error logging for {agent_id}: {e}")
                    if "connection" in str(e).lower():
                        print("[TELEMETRY] ⚠️ Disabling Qdrant - connection lost")
                        self.qdrant_ready = False
    
    def _update_requirements(self, agent_id: str, gps_data: Any, position: tuple, 
                          is_jammed: bool, jamming_level: float):
        """
        Update requirements monitor with comprehensive data
        
        Args:
            agent_id: Agent identifier
            gps_data: GPS data object
            position: Current position
            is_jammed: Jamming status
            jamming_level: Calculated jamming effect (0-100)
        """
        try:
            # Create GPSFix from gps_data
            from gps_client_lib import GPSFix
            
            # Parse the first GGA sentence for fix info
            fix_info = None
            for sentence in gps_data.nmea_sentences:
                if 'GGA' in sentence:
                    fix_info = parse_nmea_gga(sentence)
                    break
            
            if fix_info and fix_info['valid']:
                fix = GPSFix(
                    latitude=float(fix_info['latitude']) * (1 if fix_info['lat_dir'] == 'N' else -1),
                    longitude=float(fix_info['longitude']) * (1 if fix_info['lon_dir'] == 'E' else -1),
                    fix_quality=fix_info['fix_quality'],
                    satellites_used=fix_info['satellites'],
                    speed_kmh=0.0,  # No speed info in GGA
                    valid=True,
                    hdop=fix_info['hdop'],
                    altitude=fix_info['altitude']
                )
                
                # Update GPS-based requirements
                self.requirements_monitor.update_gps_fix(agent_id, fix)
                
                # Create mock satellite info based on fix quality and count
                satellites = []
                base_snr = max(0, 45 - jamming_level / 2)  # SNR degrades with jamming
                
                for i in range(fix_info['satellites']):
                    azimuth = i * (360 / fix_info['satellites'])
                    elevation = 45 + 30 * ((i % 3) - 1)  # Spread between 15-75 degrees
                    # Add some variation to SNR
                    snr = base_snr + ((i % 5) - 2)  # +/- 2dB variation
                    snr = max(10, min(50, snr))  # Keep between 10-50 dB
                    
                    satellites.append(SatelliteInfo(
                        prn=i+1,
                        elevation=elevation,
                        azimuth=azimuth,
                        snr=snr,
                        used_in_solution=(i < fix_info['fix_quality'] * 4)  # Use more sats for better fix
                    ))
                self.requirements_monitor.update_satellites(agent_id, satellites)
            
            # Update environmental conditions
            self.requirements_monitor.update_environmental_conditions(
                vehicle_id=agent_id,  # Using vehicle_id instead of agent_id
                jamming_level=jamming_level,
                gps_denied=is_jammed or jamming_level > 90
            )
            
        except Exception as e:
            print(f"[REQ] Error updating requirements for {agent_id}: {e}")
            traceback.print_exc()
    
    def _log_gps_metrics(self, agent_id: str, gps_data: Any, position: tuple):
        """
        Log GPS metrics for monitoring and analysis
        
        Args:
            agent_id: Agent identifier
            gps_data: GPS data object
            position: Current position
        """
        try:
            # Parse GGA sentence for additional metrics
            gga_parsed = {}
            for sentence in gps_data.nmea_sentences:
                if 'GGA' in sentence:
                    gga_parsed = parse_nmea_gga(sentence)
                    break
            
            fix_quality = gga_parsed.get('fix_quality', 0) if gga_parsed else 0
            satellite_count = gga_parsed.get('satellites', 0) if gga_parsed else 0
            hdop = gga_parsed.get('hdop', 99.9) if gga_parsed and gga_parsed.get('valid') else 99.9
            
            # Build log message
            log_text = (
                f"GPS metrics for {agent_id}: "
                f"Fix={fix_quality}, "
                f"Sats={satellite_count}, "
                f"HDOP={hdop:.1f}"
            )
            
            if gga_parsed.get('valid'):
                log_text += f", HDOP={gga_parsed.get('hdop', 99.9):.1f}"
            
            # Log with metadata
            log_event('gps_metrics', agent_id, position, log_text, {
                'fix_quality': fix_quality,
                'satellites': satellite_count,
                'hdop': hdop
            })
            
        except Exception as e:
            print(f"[GPS] Error logging metrics for {agent_id}: {e}")
    
    def get_agent_requirements(self, agent_id: str) -> Dict[str, Any]:
        """
        Get requirements data for an agent
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Requirements data dictionary
        """
        if self.requirements_monitor:
            return self.requirements_monitor.get_vehicle_requirements_data(agent_id)
        return {}
    
    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get comprehensive agent status
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Status dictionary with position, GPS, and jamming data
        """
        return self.agent_states.get(agent_id, {})
    
    def shutdown(self):
        """Shutdown all subsystems gracefully"""
        print("\n[SUBSYSTEMS] Initiating shutdown...")
        
        # Stop GPS manager
        if self.gps_manager:
            try:
                self.gps_manager.stop()
                print("[GPS] ✓ GPS manager stopped")
            except Exception as e:
                print(f"[GPS] ✗ Error closing GPS: {e}")
        
        # Stop requirements monitor
        if self.requirements_monitor:
            try:
                self.requirements_monitor = None
                print("[REQ] ✓ Requirements monitor stopped")
            except Exception as e:
                print(f"[REQ] ✗ Error stopping monitor: {e}")
        
        # Clear caches
        self.gps_data_cache.clear()
        self.agent_states.clear()
        
        print("[SUBSYSTEMS] ✓ Shutdown complete")