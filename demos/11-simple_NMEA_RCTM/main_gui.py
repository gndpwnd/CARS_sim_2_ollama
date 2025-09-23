#!/usr/bin/env python3
"""
Updated Main GUI with GPS Integration

Integrates satellite constellation, GPS clients, and requirements tracking.
"""

import matplotlib
matplotlib.use("Qt5Agg")
import math
import random
import sys
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import utils_gps_sim as utils
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, 
    QVBoxLayout, QWidget
)

from vehicle import Vehicle
from gps_client_lib import GPSClient
from vehicle_requirements_tracker import VehicleRequirementsTracker
from notification_gui import GPSVehicleRequirementsNotificationGUI


class GPSLocalizationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPS Localization Simulation with Requirements Tracking")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize simulation parameters
        self.simulation_bounds = (0, 100, 0, 100)
        self.gps_denied_areas = []

        # Drawing state
        self.drawing_area = False
        self.area_start = None
        self.temp_circle = None

        # Initialize vehicles
        self.vehicles = [
            Vehicle("Vehicle-1", (20, 30), "red"),
            Vehicle("Vehicle-2", (70, 20), "blue"),
            Vehicle("Vehicle-3", (50, 70), "green"),
            Vehicle("Vehicle-4", (30, 80), "orange"),
        ]

        # Simulation control
        self.running = False
        self.paused = False
        self.simulation_time = 0.0

        # GPS integration
        self.gps_clients = {}
        self.requirements_tracker = VehicleRequirementsTracker()
        self.setup_gps_integration()

        # GUI setup
        self.setup_ui()

        # Notification dashboard
        self.notification_gui = None

        # Simulation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_step)

        # Initialize plot
        self.update_plot()

    def setup_gps_integration(self):
        """Set up GPS clients and requirements tracker for all vehicles."""
        for vehicle in self.vehicles:
            # Create GPS client for each vehicle
            gps_client = GPSClient(
                vehicle_id=vehicle.id,
                server_host="localhost",
                server_port=12345,
                update_rate_hz=2.0
            )

            # Convert simulation coordinates to GPS coordinates
            lat, lon = self.sim_to_gps_coords(vehicle.position)
            gps_client.update_vehicle_state(lat, lon, 10.0)

            # Set up callbacks to update requirements tracker
            gps_client.set_fix_callback(
                lambda fix, vid=vehicle.id: self.requirements_tracker.update_gps_fix(vid, fix)
            )
            gps_client.set_satellite_callback(
                lambda sats, vid=vehicle.id: self.requirements_tracker.update_satellites(vid, sats)
            )

            self.gps_clients[vehicle.id] = gps_client

        # Add vehicles to requirements tracker
        for vehicle in self.vehicles:
            self.requirements_tracker.add_vehicle(vehicle.id)

    def sim_to_gps_coords(self, sim_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Convert simulation coordinates to GPS coordinates."""
        # Scale simulation coordinates to GPS coordinates around NYC
        lat = 40.7128 + (sim_pos[1] / 100.0) * 0.01  # Y -> latitude
        lon = -74.0060 + (sim_pos[0] / 100.0) * 0.01  # X -> longitude
        return lat, lon

    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

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
        main_layout.addWidget(plot_widget)

        # Create info panel
        self.create_info_panel(main_layout)

    def create_plot_controls(self, layout):
        """Create control buttons."""
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

        self.clear_areas_button = QPushButton("Clear Areas")
        self.clear_areas_button.setStyleSheet(
            button_style + "QPushButton { background-color: #f9aeae; color: #7f1d1d; }"
        )
        self.clear_areas_button.clicked.connect(self.clear_gps_denied_areas)

        self.dashboard_button = QPushButton("Show Dashboard")
        self.dashboard_button.setStyleSheet(
            button_style + "QPushButton { background-color: #e1d5e7; color: #4a2c4a; }"
        )
        self.dashboard_button.clicked.connect(self.toggle_dashboard)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.reset_button)
        control_layout.addWidget(self.clear_areas_button)
        control_layout.addWidget(self.dashboard_button)

        layout.addWidget(control_widget)

    def create_info_panel(self, main_layout):
        """Create information panel."""
        info_widget = QWidget()
        info_widget.setFixedWidth(350)
        info_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)
        info_layout = QVBoxLayout(info_widget)

        # Title
        title = QLabel("Vehicle Status & GPS Requirements")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                padding: 8px;
                background-color: #404040;
                border-radius: 6px;
            }
        """)
        info_layout.addWidget(title)

        # Instructions
        instructions = QLabel(
            "• Click/drag: Create GPS-denied areas\n"
            "• Red areas: GPS signal blocked\n"
            "• Green stars: Trilateration estimates\n"
            "• Dashboard: View detailed requirements"
        )
        instructions.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #cccccc;
                padding: 8px;
                background-color: #353535;
                border-radius: 4px;
            }
        """)
        instructions.setWordWrap(True)
        info_layout.addWidget(instructions)

        # Vehicle info labels
        self.vehicle_info_labels = {}
        for vehicle in self.vehicles:
            vehicle_widget = self.create_vehicle_info_widget(vehicle)
            info_layout.addWidget(vehicle_widget)

        # Simulation status
        self.sim_status_label = QLabel("Simulation: Stopped")
        self.sim_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                padding: 6px;
                background-color: #404040;
                border-radius: 4px;
            }
        """)
        info_layout.addWidget(self.sim_status_label)

        info_layout.addStretch(1)
        main_layout.addWidget(info_widget)

    def create_vehicle_info_widget(self, vehicle):
        """Create info widget for a single vehicle."""
        vehicle_widget = QWidget()
        vehicle_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #333333;
                border: 2px solid {vehicle.color};
                border-radius: 6px;
                margin: 3px;
                padding: 6px;
            }}
        """)
        
        layout = QVBoxLayout(vehicle_widget)
        
        # Vehicle header
        header = QLabel(f"{vehicle.id}")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {vehicle.color};
                padding: 3px;
                background-color: #404040;
                border-radius: 3px;
            }}
        """)
        layout.addWidget(header)

        # Status labels
        gps_label = QLabel("GPS: Connecting...")
        pos_label = QLabel("Pos: (0,0)")
        req_label = QLabel("Reqs: Checking...")

        for label in [gps_label, pos_label, req_label]:
            label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    padding: 2px;
                    color: #cccccc;
                }
            """)
            layout.addWidget(label)

        self.vehicle_info_labels[vehicle.id] = {
            "gps": gps_label,
            "position": pos_label,
            "requirements": req_label,
        }

        return vehicle_widget

    def toggle_dashboard(self):
        """Toggle the requirements dashboard."""
        if self.notification_gui is None or not self.notification_gui.isVisible():
            self.notification_gui = GPSVehicleRequirementsNotificationGUI()
            self.notification_gui.set_vehicle_tracker(self.requirements_tracker)
            self.notification_gui.show()
            self.dashboard_button.setText("Hide Dashboard")
        else:
            if self.notification_gui:
                self.notification_gui.close()
            self.dashboard_button.setText("Show Dashboard")

    def simulation_step(self):
        """Single simulation step."""
        if not self.running or self.paused:
            return

        self.simulation_time += 0.1

        for vehicle in self.vehicles:
            # Update vehicle position
            vehicle.update_position(self.simulation_bounds)

            # Check GPS denied areas
            in_denied_area = any(
                utils.is_point_in_circle(vehicle.position, (cx, cy), r)
                for cx, cy, r in self.gps_denied_areas
            )

            # Update GPS status
            if in_denied_area and vehicle.has_gps:
                vehicle.lose_gps()
                # Update GPS client conditions
                if vehicle.id in self.gps_clients:
                    self.gps_clients[vehicle.id].set_gps_conditions(
                        gps_denied=True, jamming_level=70.0
                    )
                    self.requirements_tracker.update_environmental_conditions(
                        vehicle.id, jamming_level=70.0, gps_denied=True
                    )
            elif not in_denied_area and not vehicle.has_gps:
                vehicle.regain_gps()
                if vehicle.id in self.gps_clients:
                    self.gps_clients[vehicle.id].set_gps_conditions(
                        gps_denied=False, jamming_level=0.0
                    )
                    self.requirements_tracker.update_environmental_conditions(
                        vehicle.id, jamming_level=0.0, gps_denied=False
                    )

            # Update GPS client position
            if vehicle.id in self.gps_clients:
                lat, lon = self.sim_to_gps_coords(vehicle.position)
                speed = math.sqrt(vehicle.velocity[0]**2 + vehicle.velocity[1]**2)
                heading = math.degrees(math.atan2(vehicle.velocity[1], vehicle.velocity[0])) % 360
                
                self.gps_clients[vehicle.id].update_vehicle_state(
                    lat, lon, 10.0, speed, heading
                )

            # Trilateration for vehicles without GPS
            if not vehicle.has_gps:
                anchor_vehicles = [v for v in self.vehicles if v.has_gps and v.id != vehicle.id]
                vehicle.estimate_position_via_trilateration(anchor_vehicles)

        # Update displays
        self.update_plot()
        self.update_info_panel()

    def update_info_panel(self):
        """Update the information panel with current vehicle status."""
        for vehicle in self.vehicles:
            labels = self.vehicle_info_labels[vehicle.id]
            
            # GPS status
            if vehicle.has_gps:
                labels["gps"].setText("GPS: Connected")
                labels["gps"].setStyleSheet("""
                    QLabel {
                        font-size: 10px;
                        padding: 2px 4px;
                        color: #000000;
                        font-weight: bold;
                        background-color: #4CAF50;
                        border-radius: 3px;
                    }
                """)
            else:
                labels["gps"].setText("GPS: DENIED")
                labels["gps"].setStyleSheet("""
                    QLabel {
                        font-size: 10px;
                        padding: 2px 4px;
                        color: #ffffff;
                        font-weight: bold;
                        background-color: #f44336;
                        border-radius: 3px;
                    }
                """)
            
            # Position
            labels["position"].setText(f"Pos: ({vehicle.position[0]:.1f},{vehicle.position[1]:.1f})")
            
            # Requirements status (simplified)
            metrics = self.requirements_tracker.get_vehicle_metrics(vehicle.id)
            if metrics:
                if metrics.active_satellites >= 6:
                    req_status = "Reqs: Excellent"
                    req_color = "#4CAF50"
                elif metrics.active_satellites >= 4:
                    req_status = "Reqs: Good"
                    req_color = "#FF9800"
                else:
                    req_status = "Reqs: Poor"
                    req_color = "#f44336"
            else:
                req_status = "Reqs: Unknown"
                req_color = "#555555"
            
            labels["requirements"].setText(req_status)
            labels["requirements"].setStyleSheet(f"""
                QLabel {{
                    font-size: 10px;
                    padding: 2px 4px;
                    color: #ffffff;
                    font-weight: bold;
                    background-color: {req_color};
                    border-radius: 3px;
                }}
            """)

        # Simulation status
        if self.running:
            status = f"Running ({self.simulation_time:.1f}s)"
            color = "#4CAF50"
        elif self.paused:
            status = "Paused"
            color = "#FF9800"
        else:
            status = "Stopped"
            color = "#f44336"
        
        self.sim_status_label.setText(f"Sim: {status}")
        self.sim_status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: bold;
                color: {color};
                padding: 6px;
                background-color: #404040;
                border-radius: 4px;
            }}
        """)

    def update_plot(self):
        """Update the matplotlib plot."""
        self.ax.clear()
        self.ax.set_xlim(self.simulation_bounds[0], self.simulation_bounds[1])
        self.ax.set_ylim(self.simulation_bounds[2], self.simulation_bounds[3])
        self.ax.set_xlabel("X Position (m)")
        self.ax.set_ylabel("Y Position (m)")
        self.ax.set_title("GPS Simulation with Requirements Monitoring")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect("equal")

        # Draw GPS-denied areas
        for area_center_x, area_center_y, radius in self.gps_denied_areas:
            circle = plt.Circle(
                (area_center_x, area_center_y),
                radius,
                color="red",
                alpha=0.3,
                label="GPS-Denied Area",
            )
            self.ax.add_artist(circle)

        # Draw vehicles
        for vehicle in self.vehicles:
            # Trajectory
            if len(vehicle.trajectory) > 1:
                trajectory_array = np.array(vehicle.trajectory)
                self.ax.plot(
                    trajectory_array[:, 0],
                    trajectory_array[:, 1],
                    color=vehicle.color,
                    alpha=0.3,
                    linewidth=1,
                )

            # Vehicle position
            marker_style = "o" if vehicle.has_gps else "s"
            marker_size = 8 if vehicle.has_gps else 10
            self.ax.scatter(
                *vehicle.position,
                color=vehicle.color,
                marker=marker_style,
                s=marker_size**2,
                edgecolor="black",
                linewidth=2,
                zorder=5,
            )

            # Estimated position for GPS-denied vehicles
            if vehicle.estimated_position and not vehicle.has_gps:
                self.ax.scatter(
                    *vehicle.estimated_position,
                    color="lime",
                    marker="*",
                    s=100,
                    edgecolor="darkgreen",
                    linewidth=2,
                    zorder=4,
                )

                # Error visualization
                if vehicle.position_error != float("inf"):
                    error_circle = plt.Circle(
                        vehicle.estimated_position,
                        vehicle.position_error,
                        color="lime",
                        alpha=0.2,
                        fill=True,
                    )
                    self.ax.add_artist(error_circle)

            # Vehicle label
            self.ax.annotate(
                vehicle.id,
                vehicle.position,
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color=vehicle.color,
                fontweight="bold",
            )

        # Legend
        legend_elements = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
                      markersize=8, label="GPS Available", markeredgecolor="black"),
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="gray",
                      markersize=8, label="GPS Denied", markeredgecolor="black"),
            plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="lime",
                      markersize=10, label="Estimated Position", markeredgecolor="darkgreen"),
        ]
        self.ax.legend(handles=legend_elements, loc="upper right")

        self.canvas.draw()

    def on_click(self, event):
        """Handle mouse click to start drawing GPS-denied area."""
        if event.inaxes != self.ax:
            return
        self.drawing_area = True
        self.area_start = (event.xdata, event.ydata)
        self.was_running = self.running
        if self.running:
            self.pause_simulation()

    def on_drag(self, event):
        """Handle mouse drag to preview GPS-denied area."""
        if not self.drawing_area or event.inaxes != self.ax:
            return
        radius = utils.euclidean_distance(self.area_start, (event.xdata, event.ydata))
        if self.temp_circle:
            self.temp_circle.remove()
        self.temp_circle = plt.Circle(self.area_start, radius, color="red", alpha=0.3)
        self.ax.add_artist(self.temp_circle)
        self.canvas.draw()

    def on_release(self, event):
        """Handle mouse release to finalize GPS-denied area."""
        if not self.drawing_area or event.inaxes != self.ax:
            return
        radius = utils.euclidean_distance(self.area_start, (event.xdata, event.ydata))
        if radius >= 2.0:
            self.gps_denied_areas.append((self.area_start[0], self.area_start[1], radius))
        
        self.drawing_area = False
        self.area_start = None
        if self.temp_circle:
            self.temp_circle.remove()
            self.temp_circle = None
        
        self.update_plot()
        if hasattr(self, 'was_running') and self.was_running:
            self.start_simulation()

    def start_simulation(self):
        """Start the simulation."""
        self.running = True
        self.paused = False
        
        # Start GPS clients
        for client in self.gps_clients.values():
            if not client.running:
                client.start_updates()
        
        self.timer.start(100)  # 10 FPS

    def pause_simulation(self):
        """Pause the simulation."""
        self.paused = True
        self.timer.stop()

    def reset_simulation(self):
        """Reset simulation to initial state."""
        self.running = False
        self.paused = False
        self.simulation_time = 0.0
        self.timer.stop()

        # Stop GPS clients
        for client in self.gps_clients.values():
            client.stop_updates()

        # Reset vehicles
        initial_positions = [(20, 30), (70, 20), (50, 70), (30, 80)]
        for i, vehicle in enumerate(self.vehicles):
            vehicle.position = initial_positions[i]
            vehicle.previous_position = initial_positions[i]
            vehicle.trajectory = [initial_positions[i]]
            vehicle.has_gps = True
            vehicle.estimated_position = None
            vehicle.position_error = 0.0

        # Reset GPS conditions
        for vehicle in self.vehicles:
            if vehicle.id in self.gps_clients:
                self.gps_clients[vehicle.id].set_gps_conditions(
                    gps_denied=False, jamming_level=0.0
                )
            self.requirements_tracker.update_environmental_conditions(
                vehicle.id, jamming_level=0.0, gps_denied=False
            )

        self.update_plot()
        self.update_info_panel()

    def clear_gps_denied_areas(self):
        """Clear all GPS-denied areas."""
        self.gps_denied_areas.clear()
        
        # Reset all vehicles to have GPS
        for vehicle in self.vehicles:
            if not vehicle.has_gps:
                vehicle.regain_gps()
                if vehicle.id in self.gps_clients:
                    self.gps_clients[vehicle.id].set_gps_conditions(
                        gps_denied=False, jamming_level=0.0
                    )
                self.requirements_tracker.update_environmental_conditions(
                    vehicle.id, jamming_level=0.0, gps_denied=False
                )
        
        self.update_plot()

    def closeEvent(self, event):
        """Handle main window close event."""
        # Stop GPS clients
        for client in self.gps_clients.values():
            client.stop_updates()
        
        if self.notification_gui:
            self.notification_gui.close()
        
        event.accept()


def main():
    """Main function."""
    app = QApplication(sys.argv)
    
    # Check if constellation server is running
    print("Starting GPS Simulation with Requirements Tracking")
    print("Make sure to start the satellite constellation server first:")
    print("  python sat_constellation.py")
    print("")
    
    window = GPSLocalizationGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()