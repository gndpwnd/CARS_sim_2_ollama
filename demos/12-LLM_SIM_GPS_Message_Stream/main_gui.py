#!/usr/bin/env python3
"""
Main GPS Simulation GUI (PyQt5 with embedded matplotlib)
Runs the agent simulation with visualization - NO API SERVER
"""
import matplotlib
matplotlib.use('Qt5Agg')  # Use Qt5Agg backend for PyQt5 integration

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import random
import math
import sys
import time

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)
from PyQt5.QtCore import QTimer

# Import helper functions
from sim_helper_funcs import (
    is_jammed, linear_path, limit_movement, 
    algorithm_make_move, llm_make_move,
    log_batch_of_data, get_last_safe_position,
    convert_numpy_coords
)

# Import LLM config
from llm_config import get_ollama_client, get_model_name

# Import GPS integration
try:
    from gps_client_lib import GPSData, AgentGPSManager, parse_nmea_gga
    GPS_ENABLED = True
    print("[GPS] GPS constellation integration enabled")
except ImportError as e:
    print(f"[GPS] Warning: GPS integration disabled - {e}")
    GPS_ENABLED = False

# Import requirements tracking
try:
    from sim_reqs_tracker import create_requirements_monitor, get_requirements_summary
    REQUIREMENTS_ENABLED = True
    print("[REQUIREMENTS] Requirements tracking enabled")
except ImportError as e:
    print(f"[REQUIREMENTS] Warning: Requirements tracking disabled - {e}")
    REQUIREMENTS_ENABLED = False

# Import RAG store
try:
    from rag_store import add_log
    RAG_ENABLED = True
    print("[RAG] RAG logging enabled")
except ImportError as e:
    print(f"[RAG] Warning: RAG logging disabled - {e}")
    RAG_ENABLED = False
    def add_log(text, metadata, log_id=None):
        pass

# Import PyQt5 notification dashboard
try:
    from notification_dashboard import GPSRequirementsNotificationGUI
    PYQT5_ENABLED = True
    print("[PYQT5] Notification dashboard available")
except ImportError as e:
    print(f"[PYQT5] Warning: Notification dashboard disabled - {e}")
    PYQT5_ENABLED = False

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================

USE_LLM = False
if USE_LLM:
    ollama = get_ollama_client()
    LLM_MODEL = get_model_name()
    MAX_CHARS_PER_AGENT = 25
    MAX_RETRIES = 3

# Simulation parameters
update_freq = 2.5  # seconds
max_movement_per_step = 1.41
num_history_segments = 5

# Environment setup
x_range, y_range = (-10, 10), (-10, 10)
mission_end = (10, 10)
jamming_center = (0, 0)
jamming_radius = 5

# Agent configuration
num_agents = 5
agents = [f"agent{i+1}" for i in range(num_agents)]

# Communication quality levels
high_comm_qual = 1.0
low_comm_qual = 0.2

# =============================================================================
# MAIN GUI CLASS
# =============================================================================

class GPSSimulationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Global state
        self.swarm_pos_dict = {}
        self.jammed_positions = {}
        self.last_safe_position = {}
        self.agent_paths = {}
        self.agent_targets = {}
        
        self.gps_manager = None
        self.gps_data_cache = {}
        
        self.requirements_monitor = None
        
        self.animation_running = True
        self.iteration_count = 0
        
        # PyQt5 dashboard state
        self.notification_gui = None
        
        # Setup UI
        self.setup_ui()
        
        # Initialize GPS and Requirements
        self.initialize_gps_manager()
        self.initialize_requirements_monitor()
        
        # Initialize agents
        self.initialize_agents()
        
        # Create timer for simulation updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_swarm_data)
        self.timer.start(int(update_freq * 1000))  # Convert to milliseconds
        
        # Initial plot
        self.update_plot()
    
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("Multi-Agent GPS Simulation")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header = QLabel("Multi-Agent GPS Simulation - Algorithm Control")
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(header)
        
        # Create matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.dashboard_button = QPushButton("Show Dashboard")
        self.dashboard_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.dashboard_button.clicked.connect(self.toggle_notification_dashboard)
        button_layout.addWidget(self.dashboard_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
        """)
        self.pause_button.clicked.connect(self.toggle_pause)
        button_layout.addWidget(self.pause_button)
        
        button_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Iteration: 0")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
        """)
        button_layout.addWidget(self.status_label)
        
        main_layout.addLayout(button_layout)
    
    def initialize_gps_manager(self):
        """Initialize GPS Manager"""
        if not GPS_ENABLED:
            print("[GPS] GPS integration is disabled")
            return False
        
        try:
            self.gps_manager = AgentGPSManager(
                constellation_host="localhost",
                constellation_port=12345,
                base_latitude=40.7128,
                base_longitude=-74.0060
            )
            self.gps_manager.start()
            print("[GPS] GPS manager initialized successfully")
            return True
        except Exception as e:
            print(f"[GPS] Failed to initialize GPS manager: {e}")
            return False
    
    def initialize_requirements_monitor(self):
        """Initialize Requirements Monitor"""
        if REQUIREMENTS_ENABLED:
            self.requirements_monitor = create_requirements_monitor()
            if self.requirements_monitor:
                self.requirements_monitor.start_monitoring()
                print("[REQUIREMENTS] Requirements monitoring active")
    
    def initialize_agents(self):
        """Initialize all agents"""
        print(f"[INIT] Initializing {num_agents} agents...")
        
        for agent_id in agents:
            start_pos = (
                random.uniform(x_range[0], x_range[1]),
                random.uniform(y_range[0], y_range[1])
            )
            
            self.swarm_pos_dict[agent_id] = [list(start_pos) + [high_comm_qual]]
            self.jammed_positions[agent_id] = False
            self.last_safe_position[agent_id] = start_pos
            self.agent_paths[agent_id] = []
            self.agent_targets[agent_id] = None
            
            print(f"[INIT] {agent_id} starting at {start_pos}")
            
            if GPS_ENABLED and self.gps_manager:
                self.update_agent_gps_data(agent_id, start_pos)
            
            if REQUIREMENTS_ENABLED and self.requirements_monitor:
                self.requirements_monitor.add_agent(agent_id)
    
    def update_agent_gps_data(self, agent_id, position):
        """Update GPS data for an agent"""
        if not GPS_ENABLED or self.gps_manager is None:
            return None
        
        try:
            is_agent_jammed = self.jammed_positions.get(agent_id, False)
            
            gps_data = self.gps_manager.update_agent_gps(
                agent_id=agent_id,
                position=position,
                jamming_center=jamming_center,
                jamming_radius=jamming_radius,
                gps_denied=is_agent_jammed
            )
            
            if gps_data:
                self.gps_data_cache[agent_id] = gps_data
                self.log_gps_metrics(agent_id, gps_data)
                
                if REQUIREMENTS_ENABLED and self.requirements_monitor:
                    self.requirements_monitor.update_from_gps_data(agent_id, gps_data)
                    jamming_level = self.gps_manager.calculate_jamming_level(
                        position, jamming_center, jamming_radius
                    )
                    self.requirements_monitor.update_from_simulation_state(
                        agent_id, position, is_agent_jammed, jamming_level
                    )
                
            return gps_data
            
        except Exception as e:
            print(f"[GPS] Error updating GPS for {agent_id}: {e}")
            return None
    
    def log_gps_metrics(self, agent_id, gps_data):
        """Log GPS metrics to RAG store"""
        if not RAG_ENABLED:
            return
            
        try:
            import datetime
            
            gga_parsed = {}
            for sentence in gps_data.nmea_sentences:
                if 'GGA' in sentence:
                    gga_parsed = parse_nmea_gga(sentence)
                    break
            
            timestamp = datetime.datetime.now().isoformat()
            
            log_text = (
                f"GPS metrics for {agent_id}: "
                f"Fix Quality={gps_data.fix_quality}, "
                f"Satellites={gps_data.satellite_count}, "
                f"Signal Quality={gps_data.signal_quality:.2f} dB-Hz"
            )
            
            if gga_parsed.get('valid'):
                log_text += f", HDOP={gga_parsed.get('hdop', 99.9):.1f}"
            
            metadata = {
                'timestamp': timestamp,
                'agent_id': agent_id,
                'gps_fix_quality': gps_data.fix_quality,
                'gps_satellites': gps_data.satellite_count,
                'gps_signal_quality': gps_data.signal_quality,
                'gps_hdop': gga_parsed.get('hdop', 99.9) if gga_parsed.get('valid') else 99.9,
                'nmea_sentence_count': len(gps_data.nmea_sentences),
                'rtcm_message_count': len(gps_data.rtcm_messages),
                'role': 'system',
                'source': 'gps',
                'message_type': 'gps_metrics'
            }
            
            add_log(log_text, metadata)
            
        except Exception as e:
            print(f"[GPS] Error logging GPS metrics: {e}")
    
    def update_swarm_data(self):
        """Update simulation state"""
        if not self.animation_running:
            return
            
        self.iteration_count += 1
        
        for agent_id in self.swarm_pos_dict:
            last_position = self.swarm_pos_dict[agent_id][-1][:2]
            comm_quality = self.swarm_pos_dict[agent_id][-1][2]
            is_agent_jammed = is_jammed(last_position, jamming_center, jamming_radius)
            
            if is_agent_jammed and not self.jammed_positions[agent_id]:
                print(f"{agent_id} entered jamming zone at {last_position}")
                self.jammed_positions[agent_id] = True
                self.swarm_pos_dict[agent_id][-1][2] = low_comm_qual
                
                if GPS_ENABLED:
                    self.update_agent_gps_data(agent_id, last_position)
            
            elif not is_agent_jammed and self.jammed_positions[agent_id]:
                print(f"{agent_id} left jamming zone at {last_position}")
                self.jammed_positions[agent_id] = False
                self.swarm_pos_dict[agent_id][-1][2] = high_comm_qual
                
                if GPS_ENABLED:
                    self.update_agent_gps_data(agent_id, last_position)
            
            if not self.agent_paths[agent_id] or len(self.agent_paths[agent_id]) == 0:
                if self.jammed_positions[agent_id]:
                    if USE_LLM:
                        next_pos = llm_make_move(
                            agent_id, self.swarm_pos_dict, num_history_segments,
                            ollama, LLM_MODEL, MAX_CHARS_PER_AGENT, MAX_RETRIES,
                            jamming_center, jamming_radius, max_movement_per_step,
                            x_range, y_range
                        )
                    else:
                        next_pos = algorithm_make_move(
                            agent_id, last_position, jamming_center, jamming_radius,
                            max_movement_per_step, x_range, y_range
                        )
                    
                    self.agent_paths[agent_id] = linear_path(
                        last_position, next_pos, max_movement_per_step
                    )
                
                elif self.agent_targets[agent_id]:
                    target = self.agent_targets[agent_id]
                    self.agent_paths[agent_id] = linear_path(
                        last_position, target, max_movement_per_step
                    )
                    
                    dist_to_target = math.sqrt(
                        (last_position[0] - target[0])**2 + 
                        (last_position[1] - target[1])**2
                    )
                    if dist_to_target < max_movement_per_step:
                        self.agent_targets[agent_id] = None
                        print(f"{agent_id} reached target {target}")
            
            if self.agent_paths[agent_id] and len(self.agent_paths[agent_id]) > 0:
                next_pos = self.agent_paths[agent_id].pop(0)
                limited_pos = limit_movement(last_position, next_pos, max_movement_per_step)
                
                self.swarm_pos_dict[agent_id].append([
                    limited_pos[0], 
                    limited_pos[1], 
                    low_comm_qual if self.jammed_positions[agent_id] else high_comm_qual
                ])
                
                if not self.jammed_positions[agent_id]:
                    self.last_safe_position[agent_id] = limited_pos
            
            if GPS_ENABLED and self.iteration_count % 5 == 0:
                self.update_agent_gps_data(agent_id, self.swarm_pos_dict[agent_id][-1][:2])
        
        if RAG_ENABLED and self.iteration_count % 10 == 0:
            agent_histories = {}
            for agent_id in self.swarm_pos_dict:
                last_data = self.swarm_pos_dict[agent_id][-1]
                agent_histories[agent_id] = [{
                    'position': tuple(last_data[:2]),
                    'communication_quality': last_data[2],
                    'jammed': self.jammed_positions[agent_id]
                }]
            
            log_batch_of_data(agent_histories, add_log, f"iter{self.iteration_count}")
        
        self.update_plot()
        self.status_label.setText(f"Iteration: {self.iteration_count}")
    
    def update_plot(self):
        """Update the matplotlib plot"""
        self.ax.clear()
        
        self.ax.set_xlim(x_range)
        self.ax.set_ylim(y_range)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        
        jamming_circle = patches.Circle(
            jamming_center, jamming_radius, 
            color='red', alpha=0.2, label='Jamming Zone'
        )
        self.ax.add_patch(jamming_circle)
        
        self.ax.plot(mission_end[0], mission_end[1], 'g*', markersize=20, label='Mission End')
        
        for agent_id in self.swarm_pos_dict:
            positions = self.swarm_pos_dict[agent_id]
            
            xs = [pos[0] for pos in positions]
            ys = [pos[1] for pos in positions]
            self.ax.plot(xs, ys, 'b-', alpha=0.3, linewidth=1)
            
            current = positions[-1]
            color = 'red' if self.jammed_positions[agent_id] else 'blue'
            self.ax.plot(current[0], current[1], 'o', color=color, markersize=10)
            
            label_text = f"{agent_id}\nComm: {current[2]:.1f}"
            if GPS_ENABLED and agent_id in self.gps_data_cache:
                gps = self.gps_data_cache[agent_id]
                label_text += f"\nSats: {gps.satellite_count}"
            
            self.ax.text(current[0], current[1] + 0.5, label_text, 
                    fontsize=8, ha='center')
        
        self.ax.legend(loc='upper left')
        self.ax.set_title(f'Multi-Agent GPS Simulation - Iteration {self.iteration_count}')
        
        self.canvas.draw()
    
    def toggle_notification_dashboard(self):
        """Toggle the PyQt5 notification dashboard"""
        if not PYQT5_ENABLED:
            print("[PYQT5] Notification dashboard not available")
            return
        
        if self.notification_gui is None or not self.notification_gui.isVisible():
            self.notification_gui = GPSRequirementsNotificationGUI(self.requirements_monitor)
            self.notification_gui.show()
            self.dashboard_button.setText("Hide Dashboard")
            print("[PYQT5] Notification dashboard opened")
        else:
            self.notification_gui.close()
            self.notification_gui = None
            self.dashboard_button.setText("Show Dashboard")
            print("[PYQT5] Notification dashboard closed")
    
    def toggle_pause(self):
        """Toggle simulation pause"""
        self.animation_running = not self.animation_running
        if self.animation_running:
            self.pause_button.setText("Pause")
            print("[SIM] Simulation resumed")
        else:
            self.pause_button.setText("Resume")
            print("[SIM] Simulation paused")
    
    def closeEvent(self, event):
        """Handle window close"""
        print("[SIM] Shutting down...")
        
        # Stop timer
        self.timer.stop()
        
        # Cleanup
        if self.gps_manager:
            self.gps_manager.stop()
            print("[GPS] GPS manager stopped")
        
        if self.requirements_monitor:
            self.requirements_monitor.stop_monitoring()
            print("[REQUIREMENTS] Requirements monitor stopped")
        
        # Close PyQt5 dashboard if open
        if self.notification_gui is not None:
            try:
                self.notification_gui.close()
            except:
                pass
        
        print("[SIM] Cleanup complete")
        event.accept()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main entry point"""
    print("="*60)
    print("MULTI-AGENT GPS SIMULATION - GUI")
    print("="*60)
    
    app = QApplication(sys.argv)
    window = GPSSimulationGUI()
    window.show()
    
    print("[SIM] GUI window should be visible now - simulation running...")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()