"""
Main GUI Window for GPS Localization Simulation
Handles the overall window layout and coordinates between components.
"""

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QHBoxLayout, QMainWindow, QWidget
import matplotlib.pyplot as plt

from sim_plot import SimulationPlot
from simulation.simulation_manager import SimulationManager
from gui.control_panel import ControlPanel
from gui.info_panel import InfoPanel
from gui.plot_area import PlotArea

class GPSLocalizationGUI(QMainWindow):
    """Main GUI window that orchestrates all simulation components."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPS Localization Simulation - RTK Trilateration")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize simulation manager
        self.sim_manager = SimulationManager()
        
        # Setup UI components
        self._setup_ui()
        self._setup_timer()
        self._connect_signals()
        
        # Initialize display
        self._update_display()
    
    def _setup_ui(self):
        """Initialize the user interface components."""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create matplotlib figure for plotting
        self.fig, self.ax = plt.subplots(1, 1, figsize=(10, 8))
        self.plot_manager = SimulationPlot(self.fig, self.ax)
        
        # Create UI components
        self.plot_area = PlotArea(self.plot_manager, self.sim_manager)
        self.info_panel = InfoPanel(self.sim_manager.vehicles)
        
        # Add components to main layout
        main_layout.addWidget(self.plot_area)
        main_layout.addWidget(self.info_panel)
    
    def _setup_timer(self):
        """Setup the simulation timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._simulation_step)
    
    def _connect_signals(self):
        """Connect signals between components."""
        # Connect plot area signals
        self.plot_area.start_simulation.connect(self.start_simulation)
        self.plot_area.pause_simulation.connect(self.pause_simulation)
        self.plot_area.reset_simulation.connect(self.reset_simulation)
        self.plot_area.clear_areas.connect(self.clear_gps_denied_areas)
        self.plot_area.areas_changed.connect(self._update_display)
    
    def _simulation_step(self):
        """Execute a single simulation step."""
        if not self.sim_manager.running or self.sim_manager.paused:
            return
        
        # Update simulation
        self.sim_manager.step()
        
        # Update display
        self._update_display()
    
    def _update_display(self):
        """Update all display components."""
        # Update plot
        self.plot_manager.update_plot(
            self.sim_manager.vehicles,
            self.sim_manager.gps_denied_areas,
            self.sim_manager.bounds
        )
        
        # Update info panel
        self.info_panel.update_vehicle_info(self.sim_manager.vehicles)
        self.info_panel.update_simulation_status(
            self.sim_manager.running,
            self.sim_manager.paused,
            self.sim_manager.simulation_time
        )
    
    # Simulation control methods
    def start_simulation(self):
        """Start the simulation."""
        self.sim_manager.start()
        self.timer.start(100)  # 100ms interval (10 FPS)
    
    def pause_simulation(self):
        """Pause the simulation."""
        self.sim_manager.pause()
        self.timer.stop()
    
    def reset_simulation(self):
        """Reset the simulation to initial state."""
        self.sim_manager.reset()
        self.timer.stop()
        self._update_display()
    
    def clear_gps_denied_areas(self):
        """Clear all GPS-denied areas."""
        self.sim_manager.clear_gps_denied_areas()
        self._update_display()