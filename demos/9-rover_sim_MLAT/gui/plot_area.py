"""
Plot Area Widget - Handles the matplotlib plot and user interactions.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from gui.control_panel import ControlPanel
from utils import utils

class PlotArea(QWidget):
    """Widget containing the plot and controls for drawing GPS-denied areas."""
    
    # Signals for communicating with main window  
    start_simulation = pyqtSignal()
    pause_simulation = pyqtSignal()
    reset_simulation = pyqtSignal()
    clear_areas = pyqtSignal()
    areas_changed = pyqtSignal()
    
    def __init__(self, plot_manager, sim_manager):
        super().__init__()
        self.plot_manager = plot_manager
        self.sim_manager = sim_manager
        
        # Drawing state
        self.drawing_area = False
        self.area_start = None
        self.was_running = False
        
        self._setup_ui()
        self._connect_events()
    
    def _setup_ui(self):
        """Setup the plot area UI."""
        layout = QVBoxLayout(self)
        
        # Add the plot canvas
        layout.addWidget(self.plot_manager.canvas)
        
        # Add control panel
        self.control_panel = ControlPanel()
        layout.addWidget(self.control_panel)
        
        # Connect control panel signals
        self.control_panel.start_clicked.connect(self.start_simulation.emit)
        self.control_panel.pause_clicked.connect(self.pause_simulation.emit)
        self.control_panel.reset_clicked.connect(self.reset_simulation.emit)
        self.control_panel.clear_areas_clicked.connect(self.clear_areas.emit)
        
        # Initialize plot
        self.plot_manager.setup_plot(self.sim_manager.bounds)
    
    def _connect_events(self):
        """Connect mouse events for drawing GPS-denied areas."""
        self.plot_manager.canvas.mpl_connect("button_press_event", self._on_click)
        self.plot_manager.canvas.mpl_connect("motion_notify_event", self._on_drag)
        self.plot_manager.canvas.mpl_connect("button_release_event", self._on_release)
    
    def _on_click(self, event):
        """Handle mouse click to start drawing GPS-denied area."""
        if event.inaxes != self.plot_manager.ax:
            return
        
        self.drawing_area = True
        self.area_start = (event.xdata, event.ydata)
        
        # Store current simulation state and pause if running
        self.was_running = self.sim_manager.running
        if self.sim_manager.running:
            self.pause_simulation.emit()
    
    def _on_drag(self, event):
        """Handle mouse drag to show GPS-denied area preview."""
        if not self.drawing_area or event.inaxes != self.plot_manager.ax:
            return
        
        if event.xdata is None or event.ydata is None:
            return
            
        radius = utils.euclidean_distance(
            self.area_start, 
            (event.xdata, event.ydata)
        )
        self.plot_manager.draw_temp_circle(self.area_start, radius)
    
    def _on_release(self, event):
        """Handle mouse release to finalize GPS-denied area.""" 
        if not self.drawing_area or event.inaxes != self.plot_manager.ax:
            return
            
        if event.xdata is None or event.ydata is None:
            self._cleanup_drawing()
            return
        
        # Calculate final radius and add area if valid
        radius = utils.euclidean_distance(
            self.area_start,
            (event.xdata, event.ydata)
        )
        
        if radius >= 2.0:
            self.sim_manager.add_gps_denied_area(
                self.area_start[0], 
                self.area_start[1], 
                radius
            )
        
        self._cleanup_drawing()
        
        # Emit signal to update display
        self.areas_changed.emit()
        
        # Resume simulation if it was running before drawing
        if self.was_running:
            self.start_simulation.emit()
    
    def _cleanup_drawing(self):
        """Clean up after drawing operation."""
        self.drawing_area = False
        self.area_start = None
        self.was_running = False
        self.plot_manager.clear_temp_circle()