#!/usr/bin/env python3
"""
Main GPS Simulation GUI (PyQt5 with embedded matplotlib)
Runs the agent simulation with visualization - NO API SERVER

This is the refactored entry point - most logic is in gui/ module
"""
import sys
import matplotlib
matplotlib.use('Qt5Agg')

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer, Qt

from core.config import (
    NUM_AGENTS, get_agent_ids, X_RANGE, Y_RANGE,
    DEFAULT_JAMMING_CENTER, DEFAULT_JAMMING_RADIUS, UPDATE_FREQ
)
from simulation import initialize_agents
from gui import (
    PlotManager, ControlPanel, InteractionHandler,
    SubsystemManager, SimulationUpdater
)

# ADD THESE LINES FOR SATELLITE SUPPORT
try:
    from satellite_orbital_model import SatelliteConstellation
    from integrations.satellite_integration import initialize_satellites
    SATELLITES_AVAILABLE = True
    print("[IMPORT] Satellite modules loaded successfully")
except ImportError as e:
    print(f"[IMPORT] Satellites not available: {e}")
    SATELLITES_AVAILABLE = False

print("[IMPORT] All imports completed")

class GPSSimulationGUI(QMainWindow):
    """Main GUI window for GPS simulation"""
    
    def __init__(self):
        super().__init__()
        print("[GUI] Initializing GPS Simulation GUI...")
        
        # Initialize state from simulation module
        self._initialize_state()
        
        # ADD THIS LINE: Initialize satellite constellation
        self._initialize_satellites()
        
        # Create managers
        self.plot_manager = PlotManager(self)
        self.control_panel = ControlPanel(self)
        self.interaction_handler = InteractionHandler(self)
        self.subsystem_manager = SubsystemManager(self)
        self.simulation_updater = SimulationUpdater(self)
        
        # Setup UI
        print("[GUI] Setting up UI...")
        self.control_panel.setup_ui()
        
        # Connect mouse events
        self.interaction_handler.connect_events(
            self.plot_manager.canvas,
            self.plot_manager.ax
        )
        
        # Initialize subsystems
        print("[GUI] Initializing subsystems...")
        self.subsystem_manager.initialize_all()
        
        # Expose requirements monitor for dashboard access
        self.requirements_monitor = self.subsystem_manager.requirements_monitor
        
        # Register agents with requirements monitor
        if self.requirements_monitor:
            for agent_id in get_agent_ids(NUM_AGENTS):
                self.subsystem_manager.requirements_monitor.add_vehicle(agent_id)
        
        # Schedule GPS initialization after GUI is visible
        QTimer.singleShot(500, self._initialize_gps_for_agents)
        
        # Create timer for simulation updates
        print("[GUI] Creating simulation timer...")
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_updater.update_all_agents)
        self.timer.start(int(UPDATE_FREQ * 1000))
        
        # Initial plot
        print("[GUI] Creating initial plot...")
        self.plot_manager.update_plot()
        
        print("[GUI] Initialization complete!")
        if SATELLITES_AVAILABLE and hasattr(self, 'satellite_constellation') and self.satellite_constellation:
            print(f"[GUI] ✓ Satellite visualization ENABLED ({len(self.satellite_constellation.satellites)} satellites)")
    
    def _initialize_state(self):
        """Initialize simulation state"""
        # Jamming zones
        self.jamming_zones = [(
            DEFAULT_JAMMING_CENTER[0],
            DEFAULT_JAMMING_CENTER[1],
            DEFAULT_JAMMING_RADIUS
        )]
        
        # Initialize agents
        agent_data = initialize_agents(
            num_agents=NUM_AGENTS,
            jamming_zones=self.jamming_zones,
            x_range=X_RANGE,
            y_range=Y_RANGE
        )
        
        self.swarm_pos_dict = agent_data['swarm_pos_dict']
        self.jammed_positions = agent_data['jammed_positions']
        self.last_safe_position = agent_data['last_safe_position']
        self.agent_paths = agent_data['agent_paths']
        self.agent_targets = agent_data['agent_targets']
        
        # Simulation state
        self.x_range = X_RANGE
        self.y_range = Y_RANGE
        self.animation_running = True
        self.iteration_count = 0
        self.gps_data_cache = {}
        self.notification_gui = None
        
        # Drawing mode
        self.drawing_mode = "navigate"
        
        print(f"[INIT] Initialized {NUM_AGENTS} agents")
    
    # ADD THIS NEW METHOD FOR SATELLITE INITIALIZATION
    def _initialize_satellites(self):
        """Initialize satellite constellation"""
        self.satellite_constellation = None
        
        if not SATELLITES_AVAILABLE:
            print("[SAT] Satellite modules not available, skipping initialization")
            return
        
        try:
            # Fixed orbit radius of 8 units as specified
            orbit_radius = 8.0
            
            print(f"[SAT] Initializing satellites with orbit radius: {orbit_radius}")
            self.satellite_constellation = initialize_satellites(
                config_file="constellation_config.json",
                orbit_radius=orbit_radius
            )
            
            if self.satellite_constellation:
                num_sats = len(self.satellite_constellation.satellites)
                print(f"[SAT] ✓ Successfully initialized {num_sats} satellites")
                print(f"[SAT]   - Orbit radius: {orbit_radius} units")
                print(f"[SAT]   - Satellites will orbit clockwise or counterclockwise")
            else:
                print("[SAT] ✗ Failed to initialize satellites")
                
        except Exception as e:
            print(f"[SAT] ✗ Error initializing satellites: {e}")
            import traceback
            traceback.print_exc()
            self.satellite_constellation = None
    
    def _initialize_gps_for_agents(self):
        """Initialize GPS data AFTER GUI is visible"""
        if not self.subsystem_manager.gps_manager:
            return
        
        print("[GPS] Initializing GPS data for agents...")
        for agent_id in self.swarm_pos_dict:
            position = self.swarm_pos_dict[agent_id][-1][:2]
            is_jammed = self.jammed_positions[agent_id]
            self.subsystem_manager.update_agent_gps(agent_id, position, is_jammed)
        print("[GPS] GPS data initialization complete")
    
    def closeEvent(self, event):
        """Handle window close"""
        print("[SIM] Shutting down...")
        
        self.timer.stop()
        self.subsystem_manager.shutdown()
        
        if self.notification_gui is not None:
            try:
                self.notification_gui.close()
            except:
                pass
        
        print("[SIM] Cleanup complete")
        event.accept()


def main():
    """Main entry point"""
    print("="*60)
    print("MULTI-AGENT GPS SIMULATION - GUI WITH SATELLITES")
    print("="*60)
    
    try:
        print("[MAIN] Creating QApplication...")
        app = QApplication(sys.argv)
        
        print("[MAIN] Creating main window...")
        window = GPSSimulationGUI()
        
        print("[MAIN] Showing window...")
        window.show()
        window.raise_()
        window.activateWindow()
        
        print("[SIM] GUI window should be visible now - simulation running...")
        if SATELLITES_AVAILABLE:
            print("[SIM] ✓ Satellite visualization active")
        print("[SIM] Running event loop...")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"[MAIN] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()