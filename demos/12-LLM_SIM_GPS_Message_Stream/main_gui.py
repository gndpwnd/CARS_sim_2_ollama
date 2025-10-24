#!/usr/bin/env python3
"""
Main GPS Simulation GUI (PyQt5 with embedded matplotlib)
Runs the agent simulation with visualization - NO API SERVER
"""
import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import random
import math
import sys
import time
import traceback

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)
from PyQt5.QtCore import QTimer, Qt

print("[IMPORT] Starting imports...")

from sim_helper_funcs import (
    is_jammed, linear_path, limit_movement, 
    algorithm_make_move, llm_make_move,
    log_batch_of_data, get_last_safe_position,
    convert_numpy_coords
)

from llm_config import get_ollama_client, get_model_name

try:
    from gps_client_lib import GPSData, AgentGPSManager, parse_nmea_gga
    GPS_ENABLED = True
    print("[GPS] GPS constellation integration enabled")
except ImportError as e:
    print(f"[GPS] Warning: GPS integration disabled - {e}")
    GPS_ENABLED = False

try:
    from sim_reqs_tracker import create_requirements_monitor, get_requirements_summary
    REQUIREMENTS_ENABLED = True
    print("[REQUIREMENTS] Requirements tracking enabled")
except ImportError as e:
    print(f"[REQUIREMENTS] Warning: Requirements tracking disabled - {e}")
    REQUIREMENTS_ENABLED = False

try:
    from rag_store import add_log
    RAG_ENABLED = True
    print("[RAG] RAG logging enabled")
except ImportError as e:
    print(f"[RAG] Warning: RAG logging disabled - {e}")
    RAG_ENABLED = False
    def add_log(text, metadata, log_id=None):
        pass

try:
    from notification_dashboard import GPSRequirementsNotificationGUI
    PYQT5_ENABLED = True
    print("[PYQT5] Notification dashboard available")
except ImportError as e:
    print(f"[PYQT5] Warning: Notification dashboard disabled - {e}")
    PYQT5_ENABLED = False

print("[IMPORT] All imports completed")

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
update_freq = 2.5
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
        print("[GUI] Initializing GPS Simulation GUI...")
        
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
        
        self.notification_gui = None
        
        # Jamming zones
        self.jamming_zones = [(jamming_center[0], jamming_center[1], jamming_radius)]
        
        print("[GUI] Setting up UI...")
        self.setup_ui()
        print("[GUI] UI setup complete")
        
        # Initialize GPS and Requirements (non-blocking)
        print("[GUI] Initializing subsystems...")
        self.initialize_gps_manager()
        self.initialize_requirements_monitor()
        
        # Initialize agents (NO GPS CALLS)
        print("[GUI] Initializing agents...")
        self.initialize_agents()
        
        # Create timer for simulation updates
        print("[GUI] Creating simulation timer...")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_swarm_data)
        self.timer.start(int(update_freq * 1000))
        
        # Initial plot
        print("[GUI] Creating initial plot...")
        self.update_plot()
        
        print("[GUI] Initialization complete!")
    
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("Multi-Agent GPS Simulation")
        self.setGeometry(100, 100, 1400, 900)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
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
        
        print("[GUI] Creating matplotlib figure...")
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas)
        
        button_layout = QHBoxLayout()
        
        self.mode_button = QPushButton("Mode: Navigate")
        self.mode_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.mode_button.clicked.connect(self.toggle_mode)
        button_layout.addWidget(self.mode_button)
        
        self.drawing_mode = "navigate"
        self.drawing_area = False
        self.area_start = None
        self.temp_circle = None
        
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
        
        self.clear_button = QPushButton("Clear All Jamming")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        self.clear_button.clicked.connect(self.clear_all_jamming)
        button_layout.addWidget(self.clear_button)
        
        button_layout.addStretch()
        
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
        
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
    
    def initialize_gps_manager(self):
        """Initialize GPS Manager"""
        if not GPS_ENABLED:
            print("[GPS] GPS integration is disabled")
            return False
        
        try:
            print("[GPS] Creating GPS manager...")
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
            traceback.print_exc()
            return False
    
    def initialize_requirements_monitor(self):
        """Initialize Requirements Monitor"""
        if REQUIREMENTS_ENABLED:
            try:
                print("[REQ] Creating requirements monitor...")
                self.requirements_monitor = create_requirements_monitor()
                if self.requirements_monitor:
                    self.requirements_monitor.start_monitoring()
                    print("[REQUIREMENTS] Requirements monitoring active")
                else:
                    print("[REQ] Failed to create requirements monitor")
            except Exception as e:
                print(f"[REQ] Error initializing requirements monitor: {e}")
                traceback.print_exc()
    
    def initialize_agents(self):
        """Initialize all agents - NO GPS CALLS HERE"""
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
            
            # Register with requirements monitor (no GPS needed)
            if REQUIREMENTS_ENABLED and self.requirements_monitor:
                self.requirements_monitor.add_agent(agent_id)
        
        print(f"[INIT] All {num_agents} agents initialized")
        
        # IMPORTANT: Schedule GPS initialization AFTER GUI shows
        if GPS_ENABLED and self.gps_manager:
            QTimer.singleShot(500, self.initialize_gps_for_agents)

    def initialize_gps_for_agents(self):
        """Initialize GPS data AFTER GUI is visible"""
        print("[GPS] Initializing GPS data for agents...")
        for agent_id in self.swarm_pos_dict:
            position = self.swarm_pos_dict[agent_id][-1][:2]
            self.update_agent_gps_data(agent_id, position)
        print("[GPS] GPS data initialization complete")
    
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
                    
                    jamming_level = 0.0
                    for cx, cy, radius in self.jamming_zones:
                        dist = math.sqrt((position[0] - cx)**2 + (position[1] - cy)**2)
                        if dist < radius:
                            jamming_level = max(jamming_level, 100 * (1 - dist / radius))
                    
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
            
            is_agent_jammed = self.check_if_jammed(last_position)
            
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
                            agent_id, last_position, self.get_nearest_jamming_center(last_position), 
                            self.get_nearest_jamming_radius(last_position),
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
    
    def check_if_jammed(self, position):
        """Check if a position is in any jamming zone"""
        for cx, cy, radius in self.jamming_zones:
            dist = math.sqrt((position[0] - cx)**2 + (position[1] - cy)**2)
            if dist <= radius:
                return True
        return False
    
    def get_nearest_jamming_center(self, position):
        """Get the center of the nearest jamming zone"""
        if not self.jamming_zones:
            return jamming_center
        
        min_dist = float('inf')
        nearest_center = jamming_center
        
        for cx, cy, radius in self.jamming_zones:
            dist = math.sqrt((position[0] - cx)**2 + (position[1] - cy)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_center = (cx, cy)
        
        return nearest_center
    
    def get_nearest_jamming_radius(self, position):
        """Get the radius of the nearest jamming zone"""
        if not self.jamming_zones:
            return jamming_radius
        
        min_dist = float('inf')
        nearest_radius = jamming_radius
        
        for cx, cy, radius in self.jamming_zones:
            dist = math.sqrt((position[0] - cx)**2 + (position[1] - cy)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_radius = radius
        
        return nearest_radius
    
    def update_plot(self):
        """Update the matplotlib plot"""
        try:
            self.ax.clear()
            
            self.ax.set_xlim(x_range)
            self.ax.set_ylim(y_range)
            self.ax.set_aspect('equal')
            self.ax.grid(True, alpha=0.3)
            
            for cx, cy, radius in self.jamming_zones:
                jamming_circle = patches.Circle(
                    (cx, cy), radius, 
                    color='red', alpha=0.2, label='Jamming Zone'
                )
                self.ax.add_patch(jamming_circle)
                
                self.ax.text(cx, cy, f'R={radius:.1f}', 
                           fontsize=8, ha='center', va='center',
                           bbox=dict(boxstyle='round', facecolor='red', alpha=0.3))
            
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
        except Exception as e:
            print(f"[PLOT] Error updating plot: {e}")
            traceback.print_exc()
    
    def toggle_notification_dashboard(self):
        """Toggle the PyQt5 notification dashboard"""
        if not PYQT5_ENABLED:
            print("[PYQT5] Notification dashboard not available")
            return
        
        try:
            if self.notification_gui is None or not self.notification_gui.isVisible():
                print("[PYQT5] Creating notification dashboard...")
                self.notification_gui = GPSRequirementsNotificationGUI(self.requirements_monitor)
                self.notification_gui.show()
                self.dashboard_button.setText("Hide Dashboard")
                print("[PYQT5] Notification dashboard opened")
            else:
                self.notification_gui.close()
                self.notification_gui = None
                self.dashboard_button.setText("Show Dashboard")
                print("[PYQT5] Notification dashboard closed")
        except Exception as e:
            print(f"[PYQT5] Error toggling dashboard: {e}")
            traceback.print_exc()
    
    def toggle_pause(self):
        """Toggle simulation pause"""
        self.animation_running = not self.animation_running
        if self.animation_running:
            self.pause_button.setText("Pause")
            print("[SIM] Simulation resumed")
        else:
            self.pause_button.setText("Resume")
            print("[SIM] Simulation paused")
    
    def toggle_mode(self):
        """Toggle between navigate, add jamming, and remove jamming modes"""
        modes = ["navigate", "add_jamming", "remove_jamming"]
        current_index = modes.index(self.drawing_mode)
        next_index = (current_index + 1) % len(modes)
        self.drawing_mode = modes[next_index]
        
        if self.drawing_mode == "navigate":
            self.mode_button.setText("Mode: Navigate")
            self.mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            print("[MODE] Switched to Navigate mode")
        elif self.drawing_mode == "add_jamming":
            self.mode_button.setText("Mode: Add Jamming")
            self.mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF5722;
                    color: white;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #E64A19;
                }
            """)
            print("[MODE] Switched to Add Jamming mode - Click and drag to draw jamming zone")
        else:
            self.mode_button.setText("Mode: Remove Jamming")
            self.mode_button.setStyleSheet("""
                QPushButton {
                    background-color: #9C27B0;
                    color: white;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #7B1FA2;
                }
            """)
            print("[MODE] Switched to Remove Jamming mode - Click on jamming zone to remove")
    
    def clear_all_jamming(self):
        """Clear all jamming zones"""
        self.jamming_zones.clear()
        print("[JAMMING] Cleared all jamming zones")
        self.update_plot()
    
    def on_mouse_press(self, event):
        """Handle mouse press events"""
        if event.inaxes != self.ax:
            return
        
        if self.drawing_mode == "add_jamming":
            self.drawing_area = True
            self.area_start = (event.xdata, event.ydata)
            print(f"[JAMMING] Started drawing jamming zone at ({event.xdata:.2f}, {event.ydata:.2f})")
        
        elif self.drawing_mode == "remove_jamming":
            click_pos = (event.xdata, event.ydata)
            removed = False
            
            for i, (cx, cy, radius) in enumerate(self.jamming_zones):
                dist = math.sqrt((click_pos[0] - cx)**2 + (click_pos[1] - cy)**2)
                if dist <= radius:
                    removed_zone = self.jamming_zones.pop(i)
                    print(f"[JAMMING] Removed jamming zone at ({cx:.2f}, {cy:.2f}) radius {radius:.2f}")
                    self.update_plot()
                    removed = True
                    break
            
            if not removed:
                print("[JAMMING] No jamming zone at click location")
    
    def on_mouse_move(self, event):
        """Handle mouse move events"""
        if not self.drawing_area or event.inaxes != self.ax:
            return
        
        if self.drawing_mode == "add_jamming":
            radius = math.sqrt((event.xdata - self.area_start[0])**2 + 
                             (event.ydata - self.area_start[1])**2)
            
            if self.temp_circle is not None:
                try:
                    self.temp_circle.remove()
                except:
                    pass
            
            self.temp_circle = patches.Circle(
                self.area_start, radius, 
                color='red', alpha=0.3, linestyle='--', linewidth=2
            )
            self.ax.add_patch(self.temp_circle)
            self.canvas.draw()
    
    def on_mouse_release(self, event):
        """Handle mouse release events"""
        if not self.drawing_area or event.inaxes != self.ax:
            return
        
        if self.drawing_mode == "add_jamming":
            radius = math.sqrt((event.xdata - self.area_start[0])**2 + 
                             (event.ydata - self.area_start[1])**2)
            
            if radius >= 0.5:
                self.jamming_zones.append((self.area_start[0], self.area_start[1], radius))
                print(f"[JAMMING] Added jamming zone at ({self.area_start[0]:.2f}, {self.area_start[1]:.2f}) radius {radius:.2f}")
            else:
                print("[JAMMING] Jamming zone too small, ignoring")
            
            self.drawing_area = False
            self.area_start = None
            if self.temp_circle is not None:
                try:
                    self.temp_circle.remove()
                except:
                    pass
                self.temp_circle = None
            
            self.update_plot()
    
    def closeEvent(self, event):
        """Handle window close"""
        print("[SIM] Shutting down...")
        
        self.timer.stop()
        
        if self.gps_manager:
            self.gps_manager.stop()
            print("[GPS] GPS manager stopped")
        
        if self.requirements_monitor:
            self.requirements_monitor.stop_monitoring()
            print("[REQUIREMENTS] Requirements monitor stopped")
        
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
    print("MULTI-AGENT GPS SIMULATION - GUI")
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
        
        print("[MAIN] Window visible:", window.isVisible())
        print("[MAIN] Window geometry:", window.geometry())
        
        window.setWindowFlags(window.windowFlags() & ~Qt.WindowStaysOnTopHint)
        window.show()
        
        print("[SIM] GUI window should be visible now - simulation running...")
        print("[SIM] Running event loop...")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"[MAIN] FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()