import matplotlib
matplotlib.use("Qt5Agg")
import math
import random
import sys
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from vehicle import Vehicle
from occlusion_checker import OcclusionChecker
import occlusion_utils

class OcclusionDetectionGUI(QMainWindow):
    def __init__(self, occlusion_checker, initial_drone_positions, initial_rover_position, simulation_bounds, mode_3d=False):
        super().__init__()
        self.setWindowTitle("Occlusion Detection Simulation - Geometric Analysis")
        self.setGeometry(100, 100, 1400, 900)

        # Store references to components
        self.occlusion_checker = occlusion_checker
        self.simulation_bounds = simulation_bounds
        self.mode_3d = mode_3d

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QHBoxLayout(central_widget)

        # Initialize simulation parameters
        self.obstacle_areas = []  # List of (center_x, center_y, radius) - occlusion obstacles
        self.tolerance = 0.1  # Occlusion detection tolerance in meters

        # Drawing state variables
        self.drawing_area = False
        self.area_start = None
        self.temp_circle = None

        # Initialize vehicles (drones as anchors, rover as target)
        self.drones = [
            Vehicle("Drone-1", initial_drone_positions[0], "green", is_anchor=True),
            Vehicle("Drone-2", initial_drone_positions[1], "green", is_anchor=True),
            Vehicle("Drone-3", initial_drone_positions[2], "green", is_anchor=True),
        ]
        
        # Single rover (target) - position is "unknown" to the system
        self.rover = Vehicle("Rover", initial_rover_position, "yellow", is_anchor=False)

        # Simulation control
        self.running = False
        self.paused = False
        self.simulation_time = 0.0

        # Create plot area
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)

        # Create matplotlib figure
        self.fig, self.ax = plt.subplots(1, 1, figsize=(10, 8))
        self.canvas = FigureCanvas(self.fig)
        plot_layout.addWidget(self.canvas)

        # Connect mouse events
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("motion_notify_event", self.on_drag)
        self.canvas.mpl_connect("button_release_event", self.on_release)

        # Create control buttons
        self.create_plot_controls(plot_layout)

        # Add plot widget to main layout
        main_layout.addWidget(plot_widget)

        # Create info panel
        self.create_info_panel(main_layout)

        # Create timer for simulation
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_step)

        # Initialize plot
        self.update_plot()

    def create_plot_controls(self, layout):
        """Create control buttons for the simulation."""
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)

        button_style = """
            QPushButton {
                min-width: 80px;
                min-height: 35px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #333;
                color: #000000;
            }
        """

        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(
            button_style + "QPushButton { background-color: #e3f0d8; color: #2d5016; }"
        )
        self.start_button.clicked.connect(self.start_simulation)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(
            button_style + "QPushButton { background-color: #fdf2ca; color: #8b4513; }"
        )
        self.pause_button.clicked.connect(self.pause_simulation)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setStyleSheet(
            button_style + "QPushButton { background-color: #d8e3f0; color: #1e3a8a; }"
        )
        self.reset_button.clicked.connect(self.reset_simulation)

        self.clear_areas_button = QPushButton("Clear Obstacles")
        self.clear_areas_button.setStyleSheet(
            button_style + "QPushButton { background-color: #f9aeae; color: #7f1d1d; }"
        )
        self.clear_areas_button.clicked.connect(self.clear_obstacles)

        # Add 3D mode toggle
        self.mode_3d_checkbox = QCheckBox("3D Mode")
        self.mode_3d_checkbox.setChecked(self.mode_3d)
        self.mode_3d_checkbox.stateChanged.connect(self.toggle_3d_mode)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.reset_button)
        control_layout.addWidget(self.clear_areas_button)
        control_layout.addWidget(self.mode_3d_checkbox)

        layout.addWidget(control_widget)

    def create_info_panel(self, main_layout):
        """Create information panel showing occlusion status."""
        info_widget = QWidget()
        info_widget.setFixedWidth(350)
        info_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        title_label = QLabel("Occlusion Detection Status")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                padding: 8px;
                background-color: #404040;
                border-radius: 6px;
                border: 1px solid #555555;
            }
        """)
        info_layout.addWidget(title_label)
        
        # Instructions
        mode_text = "3D" if self.mode_3d else "2D"
        instructions = QLabel(f"• Click/drag: Obstacle areas\n• Red areas: Signal obstacles\n• Mode: {mode_text}\n• Tolerance: {self.tolerance}m")
        instructions.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #cccccc;
                padding: 8px;
                background-color: #353535;
                border-radius: 4px;
                border: 1px solid #555555;
                font-weight: 500;
            }
        """)
        instructions.setWordWrap(True)
        info_layout.addWidget(instructions)
        
        # Drone status
        self.drone_info_labels = {}
        for drone in self.drones:
            drone_widget = QWidget()
            drone_widget.setStyleSheet(f"""
                QWidget {{
                    background-color: #333333;
                    border: 2px solid {drone.color};
                    border-radius: 6px;
                    margin: 3px;
                    padding: 6px;
                }}
            """)
            drone_layout = QVBoxLayout(drone_widget)
            drone_layout.setSpacing(4)
            drone_layout.setContentsMargins(6, 6, 6, 6)
            
            # Drone header
            header = QLabel(f"{drone.id}")
            header.setStyleSheet(f"""
                QLabel {{
                    font-size: 13px;
                    font-weight: bold;
                    color: {drone.color};
                    padding: 3px;
                    background-color: #404040;
                    border-radius: 3px;
                }}
            """)
            drone_layout.addWidget(header)
            
            # Status display
            status_label = QLabel("Status: Clear")
            status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    padding: 2px 4px;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
            
            distance_label = QLabel("Distance: 0.0m")
            distance_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    padding: 2px;
                    color: #cccccc;
                    font-weight: 500;
                }
            """)
            
            drone_layout.addWidget(status_label)
            drone_layout.addWidget(distance_label)
            
            self.drone_info_labels[drone.id] = {
                "status": status_label,
                "distance": distance_label,
            }
            
            info_layout.addWidget(drone_widget)
        
        # Rover status
        rover_widget = QWidget()
        rover_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #333333;
                border: 2px solid {self.rover.color};
                border-radius: 6px;
                margin: 3px;
                padding: 6px;
            }}
        """)
        rover_layout = QVBoxLayout(rover_widget)
        rover_layout.setSpacing(4)
        rover_layout.setContentsMargins(6, 6, 6, 6)
        
        rover_header = QLabel("Rover (Target)")
        rover_header.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {self.rover.color};
                padding: 3px;
                background-color: #404040;
                border-radius: 3px;
            }}
        """)
        rover_layout.addWidget(rover_header)
        
        self.rover_occlusion_label = QLabel("Occlusion: None")
        self.rover_occlusion_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                padding: 2px 4px;
                font-weight: bold;
                border-radius: 3px;
            }
        """)
        rover_layout.addWidget(self.rover_occlusion_label)
        
        info_layout.addWidget(rover_widget)
        
        # Simulation status
        self.sim_status_label = QLabel("Simulation: Stopped")
        self.sim_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #ffffff;
                padding: 6px;
                background-color: #404040;
                border-radius: 4px;
                border: 1px solid #555555;
            }
        """)
        info_layout.addWidget(self.sim_status_label)
        
        info_layout.addStretch(1)
        main_layout.addWidget(info_widget)

    def update_info_panel(self):
        """Update the information panel with current occlusion status."""
        # Get current distances from rover to all drones
        drone_positions = [drone.position for drone in self.drones]
        distances = []
        
        for drone in self.drones:
            distance = occlusion_utils.euclidean_distance(self.rover.position, drone.position)
            # Add some realistic measurement noise
            distance += random.gauss(0, 0.05)  # 5cm standard deviation
            distances.append(distance)
        
        # Check for occlusion
        occlusion_results = self.occlusion_checker.check_occlusion(drone_positions, distances)
        
        # Update drone info labels
        for i, drone in enumerate(self.drones):
            labels = self.drone_info_labels[drone.id]
            
            # Update distance
            labels["distance"].setText(f"Distance: {distances[i]:.2f}m")
            
            # Update occlusion status
            is_occluded = i in occlusion_results['occluded_anchors']
            if is_occluded:
                status_text = "OCCLUDED"
                status_color = "#ffffff"
                status_bg = "#f44336"  # Red
            else:
                status_text = "Clear"
                status_color = "#000000"
                status_bg = "#4CAF50"  # Green
            
            labels["status"].setText(f"Status: {status_text}")
            labels["status"].setStyleSheet(f"""
                QLabel {{
                    font-size: 10px;
                    padding: 2px 4px;
                    color: {status_color};
                    font-weight: bold;
                    background-color: {status_bg};
                    border-radius: 3px;
                }}
            """)
        
        # Update rover occlusion status
        if occlusion_results['is_occluded']:
            occluded_count = len(occlusion_results['occluded_anchors'])
            confidence = occlusion_results['confidence_score']
            occlusion_text = f"Detected: {occluded_count} drones (conf: {confidence:.2f})"
            occlusion_color = "#ffffff"
            occlusion_bg = "#f44336"  # Red
        else:
            occlusion_text = "None detected"
            occlusion_color = "#000000"
            occlusion_bg = "#4CAF50"  # Green
        
        self.rover_occlusion_label.setText(f"Occlusion: {occlusion_text}")
        self.rover_occlusion_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                padding: 2px 4px;
                color: {occlusion_color};
                font-weight: bold;
                background-color: {occlusion_bg};
                border-radius: 3px;
            }}
        """)
        
        # Update simulation status
        if self.running:
            status = f"Running ({self.simulation_time:.1f}s)"
            color = "#4CAF50"
            bg_color = "#2E7D32"
        elif self.paused:
            status = "Paused"
            color = "#FF9800"
            bg_color = "#E65100"
        else:
            status = "Stopped"
            color = "#f44336"
            bg_color = "#C62828"
        
        self.sim_status_label.setText(f"Sim: {status}")
        self.sim_status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: bold;
                color: {color};
                padding: 6px;
                background-color: {bg_color};
                border-radius: 4px;
                border: 1px solid {color};
            }}
        """)

    def simulation_step(self):
        """Single step of the simulation."""
        if not self.running or self.paused:
            return

        # Update simulation time
        self.simulation_time += 0.1

        # Update rover position (target moves around)
        self.rover.update_position(self.simulation_bounds)
        
        # Optionally move drones slightly (they can move to avoid occlusion)
        for drone in self.drones:
            drone.update_position(self.simulation_bounds, movement_scale=0.1)  # Slower movement

        # Update display
        self.update_plot()
        self.update_info_panel()

    def update_plot(self):
        """Update the matplotlib plot."""
        self.ax.clear()

        # Set up plot
        self.ax.set_xlim(self.simulation_bounds[0], self.simulation_bounds[1])
        self.ax.set_ylim(self.simulation_bounds[2], self.simulation_bounds[3])
        self.ax.set_xlabel("X Position (m)")
        self.ax.set_ylabel("Y Position (m)")
        mode_text = "3D" if self.mode_3d else "2D"
        self.ax.set_title(f"Occlusion Detection Simulation ({mode_text} Mode)")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect("equal")

        # Draw obstacle areas
        for area_center_x, area_center_y, radius in self.obstacle_areas:
            circle = plt.Circle(
                (area_center_x, area_center_y),
                radius,
                color="red",
                alpha=0.3,
                label="Obstacle Area",
            )
            self.ax.add_artist(circle)

        # Get current distances and occlusion status
        drone_positions = [drone.position for drone in self.drones]
        distances = []
        
        for drone in self.drones:
            distance = occlusion_utils.euclidean_distance(self.rover.position, drone.position)
            distance += random.gauss(0, 0.05)  # Add measurement noise
            distances.append(distance)
        
        occlusion_results = self.occlusion_checker.check_occlusion(drone_positions, distances)

        # Draw drones (anchors)
        for i, drone in enumerate(self.drones):
            # Draw trajectory
            if len(drone.trajectory) > 1:
                trajectory_array = np.array(drone.trajectory)
                self.ax.plot(
                    trajectory_array[:, 0],
                    trajectory_array[:, 1],
                    color=drone.color,
                    alpha=0.3,
                    linewidth=1,
                )

            # Check if this drone is occluded
            is_occluded = i in occlusion_results['occluded_anchors']
            marker_style = "s" if is_occluded else "o"  # Square if occluded, circle if clear
            edge_color = "red" if is_occluded else "black"
            
            self.ax.scatter(
                *drone.position,
                color=drone.color,
                marker=marker_style,
                s=100,
                edgecolor=edge_color,
                linewidth=3,
                zorder=5,
            )

            # Draw distance measurement lines (dotted blue)
            self.ax.plot(
                [self.rover.position[0], drone.position[0]],
                [self.rover.position[1], drone.position[1]],
                color='blue',
                linestyle=':',
                linewidth=2,
                alpha=0.7,
                zorder=3
            )
            
            # Add distance labels
            mid_x = (self.rover.position[0] + drone.position[0]) / 2
            mid_y = (self.rover.position[1] + drone.position[1]) / 2
            self.ax.text(mid_x, mid_y, f'{distances[i]:.1f}m', 
                        ha='center', va='center', fontsize=9, 
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='lightblue', alpha=0.8))

            # Add drone label
            self.ax.annotate(
                drone.id,
                drone.position,
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=10,
                color=drone.color,
                fontweight="bold",
            )

        # Draw rover (target)
        rover_trajectory_array = np.array(self.rover.trajectory) if len(self.rover.trajectory) > 1 else np.array([self.rover.position])
        if len(self.rover.trajectory) > 1:
            self.ax.plot(
                rover_trajectory_array[:, 0],
                rover_trajectory_array[:, 1],
                color=self.rover.color,
                alpha=0.3,
                linewidth=2,
            )
        
        self.ax.scatter(
            *self.rover.position,
            color=self.rover.color,
            marker="o",
            s=120,
            edgecolor="black",
            linewidth=2,
            zorder=6,
        )
        
        # Add rover label
        self.ax.annotate(
            "Rover",
            self.rover.position,
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=10,
            color=self.rover.color,
            fontweight="bold",
        )

        # Add legend
        legend_elements = []
        legend_elements.append(
            plt.Line2D(
                [0], [0], marker="o", color="w", markerfacecolor="green",
                markersize=8, label="Drone (Clear)", markeredgecolor="black"
            )
        )
        legend_elements.append(
            plt.Line2D(
                [0], [0], marker="s", color="w", markerfacecolor="green",
                markersize=8, label="Drone (Occluded)", markeredgecolor="red"
            )
        )
        legend_elements.append(
            plt.Line2D(
                [0], [0], marker="o", color="w", markerfacecolor="yellow",
                markersize=10, label="Rover (Target)", markeredgecolor="black"
            )
        )
        legend_elements.append(
            plt.Line2D(
                [0], [0], color="blue", linestyle=":", linewidth=2,
                label="Distance Measurement"
            )
        )

        self.ax.legend(handles=legend_elements, loc="upper right")

        # Draw canvas
        self.canvas.draw()

    def on_click(self, event):
        """Handle mouse click to start drawing obstacle area."""
        if event.inaxes != self.ax:
            return

        self.drawing_area = True
        self.area_start = (event.xdata, event.ydata)
        
        # Store current simulation state before pausing
        self.was_running = self.running
        
        # Pause simulation while drawing
        if self.running:
            self.pause_simulation()

    def on_drag(self, event):
        """Handle mouse drag to show obstacle area preview."""
        if not self.drawing_area or event.inaxes != self.ax:
            return

        # Calculate radius
        radius = occlusion_utils.euclidean_distance(self.area_start, (event.xdata, event.ydata))

        # Remove previous temporary circle
        if self.temp_circle is not None:
            self.temp_circle.remove()

        # Draw new temporary circle
        self.temp_circle = plt.Circle(self.area_start, radius, color="red", alpha=0.3)
        self.ax.add_artist(self.temp_circle)
        self.canvas.draw()

    def on_release(self, event):
        """Handle mouse release to finalize obstacle area."""
        if not self.drawing_area or event.inaxes != self.ax:
            return

        # Calculate final radius
        radius = occlusion_utils.euclidean_distance(self.area_start, (event.xdata, event.ydata))

        # Add obstacle area (minimum radius of 2)
        if radius >= 2.0:
            self.obstacle_areas.append(
                (self.area_start[0], self.area_start[1], radius)
            )

        # Clean up
        self.drawing_area = False
        self.area_start = None
        if self.temp_circle is not None:
            self.temp_circle.remove()
            self.temp_circle = None

        # Update plot
        
        # Resume simulation if it was running before drawing
        if hasattr(self, 'was_running') and self.was_running:
            self.start_simulation()
            self.was_running = False

    def toggle_3d_mode(self, state):
        """Toggle between 2D and 3D mode."""
        self.mode_3d = state == 2  # Qt checkbox state: 2 = checked, 0 = unchecked
        self.occlusion_checker.mode_3d = self.mode_3d
        self.update_plot()
        print(f"Mode switched to: {'3D' if self.mode_3d else '2D'}")

    def start_simulation(self):
        """Start the simulation."""
        self.running = True
        self.paused = False
        self.timer.start(100)  # 100ms interval (10 FPS)

    def pause_simulation(self):
        """Pause the simulation."""
        self.paused = True
        self.timer.stop()

    def reset_simulation(self):
        """Reset the simulation to initial state."""
        self.running = False
        self.paused = False
        self.simulation_time = 0.0
        self.timer.stop()

        # Reset vehicle positions and states
        initial_drone_positions = [(20, 20), (80, 20), (50, 80)]
        for i, drone in enumerate(self.drones):
            drone.reset_to_position(initial_drone_positions[i])
        
        self.rover.reset_to_position((50, 40))

        self.update_plot()
        self.update_info_panel()

    def clear_obstacles(self):
        """Clear all obstacle areas."""
        self.obstacle_areas.clear()
        self.update_plot()