"""
Information Panel Widget - Displays vehicle status and simulation info.
"""

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QHBoxLayout

class InfoPanel(QWidget):
    """Widget displaying vehicle status and simulation information."""
    
    def __init__(self, vehicles):
        super().__init__()
        self.vehicles = vehicles
        self.vehicle_info_labels = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the information panel UI."""
        self.setFixedWidth(350)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Add title and instructions
        self._add_header(layout)
        
        # Add vehicle info sections
        self._add_vehicle_info(layout)
        
        # Add simulation status
        self._add_simulation_status(layout)
        
        layout.addStretch(1)
    
    def _add_header(self, layout):
        """Add title and instructions to the panel."""
        title_label = QLabel("Vehicle Status")
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
        layout.addWidget(title_label)
        
        instructions = QLabel(
            "• Click/drag: GPS-denied areas\n"
            "• Red areas: GPS loss\n"
            "• Green stars: Estimates\n"
            "• Need ≥3 GPS for trilateration"
        )
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
        layout.addWidget(instructions)
    
    def _add_vehicle_info(self, layout):
        """Add vehicle information sections."""
        for vehicle in self.vehicles:
            vehicle_widget = self._create_vehicle_widget(vehicle)
            layout.addWidget(vehicle_widget)
    
    def _create_vehicle_widget(self, vehicle):
        """Create a widget for displaying individual vehicle information."""
        vehicle_widget = QWidget()
        vehicle_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #333333;
                border: 2px solid {vehicle['color']};
                border-radius: 6px;
                margin: 3px;
                padding: 6px;
            }}
        """)
        
        vehicle_layout = QVBoxLayout(vehicle_widget)
        vehicle_layout.setSpacing(4)
        vehicle_layout.setContentsMargins(6, 6, 6, 6)
        
        # Vehicle header
        header = QLabel(f"{vehicle['id']}")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {vehicle['color']};
                padding: 3px;
                background-color: #404040;
                border-radius: 3px;
            }}
        """)
        vehicle_layout.addWidget(header)
        
        # GPS status and position
        gps_pos_widget = QWidget()
        gps_pos_layout = QHBoxLayout(gps_pos_widget)
        gps_pos_layout.setContentsMargins(0, 0, 0, 0)
        gps_pos_layout.setSpacing(8)
        
        gps_label = QLabel("GPS: OK")
        gps_label.setStyleSheet(self._get_label_style(10))
        
        pos_label = QLabel("Pos: (0,0)")
        pos_label.setStyleSheet(self._get_label_style(10, "#cccccc"))
        
        gps_pos_layout.addWidget(gps_label)
        gps_pos_layout.addWidget(pos_label)
        gps_pos_layout.addStretch()
        
        # Estimate and error
        est_err_widget = QWidget()
        est_err_layout = QHBoxLayout(est_err_widget)
        est_err_layout.setContentsMargins(0, 0, 0, 0)
        est_err_layout.setSpacing(8)
        
        est_label = QLabel("Est: N/A")
        est_label.setStyleSheet(self._get_label_style(10, "#aaaaaa"))
        
        error_label = QLabel("Err: 0m")
        error_label.setStyleSheet(self._get_label_style(10))
        
        est_err_layout.addWidget(est_label)
        est_err_layout.addWidget(error_label)
        est_err_layout.addStretch()
        
        vehicle_layout.addWidget(gps_pos_widget)
        vehicle_layout.addWidget(est_err_widget)
        
        # Store references to labels for updates
        self.vehicle_info_labels[vehicle['id']] = {
            "gps": gps_label,
            "position": pos_label,
            "estimated": est_label,
            "error": error_label,
        }
        
        return vehicle_widget
    
    def _add_simulation_status(self, layout):
        """Add simulation status label."""
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
        layout.addWidget(self.sim_status_label)
    
    def _get_label_style(self, font_size, color="#ffffff"):
        """Get common label styling."""
        return f"""
            QLabel {{
                font-size: {font_size}px;
                padding: 2px;
                color: {color};
                font-weight: 500;
            }}
        """
    
    def update_vehicle_info(self, vehicles):
        """Update vehicle information display."""
        for vehicle in vehicles:
            if vehicle['id'] not in self.vehicle_info_labels:
                continue
                
            labels = self.vehicle_info_labels[vehicle['id']]
            
            # Update GPS status
            self._update_gps_status(labels["gps"], vehicle['has_gps'])
            
            # Update position
            pos_text = f"({vehicle['position'][0]:.1f},{vehicle['position'][1]:.1f})"
            labels["position"].setText(f"Pos: {pos_text}")
            
            # Update estimated position
            self._update_estimated_position(labels["estimated"], vehicle['estimated_position'])
            
            # Update error
            self._update_error_display(labels["error"], vehicle['position_error'])
    
    def _update_gps_status(self, label, has_gps):
        """Update GPS status display."""
        status = "OK" if has_gps else "DENIED"
        if has_gps:
            style = self._get_status_style("#000000", "#4CAF50")
        else:
            style = self._get_status_style("#ffffff", "#f44336")
        
        label.setText(f"GPS: {status}")
        label.setStyleSheet(style)
    
    def _update_estimated_position(self, label, estimated_position):
        """Update estimated position display."""
        if estimated_position:
            est_text = f"({estimated_position[0]:.1f},{estimated_position[1]:.1f})"
            label.setText(f"Est: {est_text}")
            label.setStyleSheet(self._get_label_style(10, "#64B5F6"))
        else:
            label.setText("Est: N/A")
            label.setStyleSheet(self._get_label_style(10, "#aaaaaa"))
    
    def _update_error_display(self, label, position_error):
        """Update position error display."""
        if position_error != float("inf"):
            error_text = f"{position_error:.1f}m"
            if position_error > 2.0:
                style = self._get_status_style("#ffffff", "#f44336")
            elif position_error > 1.0:
                style = self._get_status_style("#000000", "#FF9800")
            else:
                style = self._get_status_style("#000000", "#4CAF50")
            
            label.setText(f"Err: {error_text}")
            label.setStyleSheet(style)
        else:
            label.setText("Err: Need≥3GPS")
            label.setStyleSheet(self._get_status_style("#cccccc", "#555555"))
    
    def _get_status_style(self, text_color, bg_color):
        """Get styling for status labels with background colors."""
        return f"""
            QLabel {{
                font-size: 10px;
                padding: 2px 4px;
                color: {text_color};
                font-weight: bold;
                background-color: {bg_color};
                border-radius: 3px;
            }}
        """
    
    def update_simulation_status(self, running, paused, simulation_time):
        """Update simulation status display."""
        if running:
            status = f"Running ({simulation_time:.1f}s)"
            color = "#4CAF50"
            bg_color = "#2E7D32"
        elif paused:
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