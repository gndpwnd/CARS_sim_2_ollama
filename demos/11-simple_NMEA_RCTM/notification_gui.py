#!/usr/bin/env python3
"""
Simplified GPS Requirements Notification GUI

Features vehicle dropdown selector and simplified requirements monitoring.
"""

import sys
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QScrollArea, QGridLayout, QFrame, QTabWidget, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QColor

from vehicle_requirements_tracker import VehicleRequirementsTracker


class RequirementIndicator(QFrame):
    """Individual requirement status indicator."""
    
    def __init__(self, name: str, current_value: float, threshold: float, 
                 warning_threshold: float, unit: str):
        super().__init__()
        self.name = name
        self.current_value = current_value
        self.threshold = threshold
        self.warning_threshold = warning_threshold
        self.unit = unit
        self.setup_ui()
        self.update_display()
    
    def setup_ui(self):
        """Set up the indicator UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        
        # Name label
        self.name_label = QLabel(self.name)
        self.name_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Value display
        self.value_label = QLabel()
        self.value_label.setFont(QFont("Arial", 8))
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)
        
        # Status display
        self.status_label = QLabel()
        self.status_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setFixedSize(140, 80)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
    
    def update_values(self, current_value: float, threshold: float, 
                     warning_threshold: float):
        """Update the indicator values."""
        self.current_value = current_value
        self.threshold = threshold
        self.warning_threshold = warning_threshold
        self.update_display()
    
    def update_display(self):
        """Update the visual display."""
        # Format value
        if isinstance(self.current_value, float):
            if self.current_value < 1:
                self.value_label.setText(f"{self.current_value:.3f} {self.unit}")
            else:
                self.value_label.setText(f"{self.current_value:.1f} {self.unit}")
        else:
            self.value_label.setText(f"{self.current_value} {self.unit}")
        
        # Determine status and color
        status, color, text_color = self.get_status_color()
        self.status_label.setText(status)
        
        # Apply styling
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border: 2px solid #333333;
                border-radius: 6px;
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
        """)
    
    def get_status_color(self):
        """Determine status and color based on current value."""
        # Identify error metrics (lower is better)
        error_keywords = [
            'error', 'failure', 'degradation', 'slip', 'drop', 'variance',
            'drift', 'diff', 'jump', 'oscillation', 'activity', 'rate', 'anomaly'
        ]
        
        is_error_metric = any(keyword in self.name.lower() for keyword in error_keywords)
        
        if is_error_metric:
            # For error metrics: lower is better
            if self.current_value <= self.warning_threshold:
                return "OK", "#4CAF50", "#FFFFFF"
            elif self.current_value <= self.threshold:
                return "WARNING", "#FF9800", "#000000"
            else:
                return "CRITICAL", "#F44336", "#FFFFFF"
        else:
            # For quality metrics: higher is better
            if self.current_value >= self.warning_threshold:
                return "OK", "#4CAF50", "#FFFFFF"
            elif self.current_value >= self.threshold:
                return "WARNING", "#FF9800", "#000000"
            else:
                return "CRITICAL", "#F44336", "#FFFFFF"


class SubsectionPanel(QWidget):
    """Panel for a subsection containing multiple indicators."""
    
    def __init__(self, subsection_name: str, requirements: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.subsection_name = subsection_name
        self.indicators = {}
        self.setup_ui(requirements)
    
    def setup_ui(self, requirements: Dict[str, Dict[str, Any]]):
        """Set up the subsection UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel(self.subsection_name)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: #555555;
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #777777;
            }
        """)
        layout.addWidget(title_label)
        
        # Grid for indicators
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(8)
        
        # Add indicators
        row, col = 0, 0
        max_cols = 4
        
        for req_name, req_data in requirements.items():
            indicator = RequirementIndicator(
                req_data['name'],
                req_data.get('current_value', 0),
                req_data['threshold'],
                req_data['warning_threshold'],
                req_data['unit']
            )
            self.indicators[req_name] = indicator
            
            grid_layout.addWidget(indicator, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        layout.addWidget(grid_widget)
        layout.addStretch()
    
    def update_indicators(self, updated_requirements: Dict[str, Dict[str, Any]]):
        """Update all indicators in this subsection."""
        for req_name, indicator in self.indicators.items():
            if req_name in updated_requirements:
                req_data = updated_requirements[req_name]
                indicator.update_values(
                    req_data.get('current_value', 0),
                    req_data['threshold'],
                    req_data['warning_threshold']
                )


class SectionTab(QScrollArea):
    """Scrollable tab for a major section."""
    
    def __init__(self, section_name: str, section_data: Dict[str, Dict[str, Dict[str, Any]]]):
        super().__init__()
        self.section_name = section_name
        self.subsection_panels = {}
        self.setup_ui(section_data)
    
    def setup_ui(self, section_data: Dict[str, Dict[str, Dict[str, Any]]]):
        """Set up the section tab UI."""
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Main content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add subsection panels
        for subsection_name, subsection_data in section_data.items():
            panel = SubsectionPanel(subsection_name, subsection_data)
            self.subsection_panels[subsection_name] = panel
            content_layout.addWidget(panel)
        
        content_layout.addStretch()
        self.setWidget(content_widget)
    
    def update_section(self, updated_section_data: Dict[str, Dict[str, Dict[str, Any]]]):
        """Update all subsections in this section."""
        for subsection_name, panel in self.subsection_panels.items():
            if subsection_name in updated_section_data:
                panel.update_indicators(updated_section_data[subsection_name])


class GPSVehicleRequirementsNotificationGUI(QMainWindow):
    """Main notification GUI with vehicle dropdown."""
    
    def __init__(self):
        super().__init__()
        self.vehicle_tracker: Optional[VehicleRequirementsTracker] = None
        self.section_tabs = {}
        self.current_vehicle_id = None
        self.setup_ui()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_data)
        self.update_timer.start(1000)  # Update every second
    
    def setup_ui(self):
        """Set up the main UI."""
        self.setWindowTitle("GPS Requirements Dashboard")
        self.setGeometry(200, 200, 1200, 800)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #353535;
            }
            QTabBar::tab {
                background-color: #404040;
                color: #FFFFFF;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #555555;
                border-bottom: 2px solid #4CAF50;
            }
            QComboBox {
                background-color: #404040;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 12px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #555555;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                color: #FFFFFF;
                selection-background-color: #555555;
                border: 1px solid #555555;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header with title and controls
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        
        # Title
        title_label = QLabel("GPS Requirements Dashboard")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: #404040;
                padding: 12px;
                border-radius: 6px;
                border: 2px solid #555555;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        # Controls
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        
        # Vehicle selector
        vehicle_label = QLabel("Vehicle:")
        vehicle_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        self.vehicle_selector = QComboBox()
        self.vehicle_selector.addItem("No vehicles available", None)
        self.vehicle_selector.currentTextChanged.connect(self.on_vehicle_changed)
        
        # Status
        self.status_label = QLabel("Status: Not Connected")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #FF4444;
                background-color: #333333;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        
        controls_layout.addWidget(vehicle_label)
        controls_layout.addWidget(self.vehicle_selector)
        controls_layout.addStretch()
        controls_layout.addWidget(self.status_label)
        
        header_layout.addWidget(controls_widget)
        layout.addWidget(header_widget)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Initially show placeholder
        self.show_placeholder()
    
    def show_placeholder(self):
        """Show placeholder when no data available."""
        self.tab_widget.clear()
        placeholder = QLabel("Select a vehicle to view GPS requirements.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #888888; font-size: 14px; padding: 20px;")
        self.tab_widget.addTab(placeholder, "No Data")
    
    def set_vehicle_tracker(self, tracker: VehicleRequirementsTracker):
        """Set the vehicle tracker and start monitoring."""
        self.vehicle_tracker = tracker
        self.status_label.setText("Status: Connected")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #44AA44;
                background-color: #333333;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        self.update_vehicle_list()
    
    def update_vehicle_list(self):
        """Update the vehicle selector dropdown."""
        if not self.vehicle_tracker:
            return
        
        current_selection = self.vehicle_selector.currentData()
        vehicle_ids = self.vehicle_tracker.get_all_vehicle_ids()
        
        # Update dropdown
        self.vehicle_selector.blockSignals(True)
        self.vehicle_selector.clear()
        
        if vehicle_ids:
            for vehicle_id in sorted(vehicle_ids):
                self.vehicle_selector.addItem(vehicle_id, vehicle_id)
            
            # Restore selection or select first
            if current_selection in vehicle_ids:
                index = self.vehicle_selector.findData(current_selection)
                if index >= 0:
                    self.vehicle_selector.setCurrentIndex(index)
            else:
                self.vehicle_selector.setCurrentIndex(0)
        else:
            self.vehicle_selector.addItem("No vehicles available", None)
        
        self.vehicle_selector.blockSignals(False)
        self.on_vehicle_changed()
    
    def on_vehicle_changed(self):
        """Handle vehicle selection change."""
        self.current_vehicle_id = self.vehicle_selector.currentData()
        if self.current_vehicle_id:
            self.refresh_data()
        else:
            self.show_placeholder()
    
    def refresh_data(self):
        """Refresh data for current vehicle."""
        if not self.vehicle_tracker or not self.current_vehicle_id:
            return
        
        # Get requirements data
        data = self.vehicle_tracker.get_vehicle_requirements_data(self.current_vehicle_id)
        if not data:
            return
        
        # Update or create tabs
        if not self.section_tabs or set(data.keys()) != set(self.section_tabs.keys()):
            self.create_tabs(data)
        else:
            # Update existing tabs
            for section_name, tab in self.section_tabs.items():
                if section_name in data:
                    tab.update_section(data[section_name])
        
        # Update tab indicators
        self.update_tab_indicators(data)
    
    def create_tabs(self, data: Dict[str, Any]):
        """Create tabs for each section."""
        self.tab_widget.clear()
        self.section_tabs.clear()
        
        for section_name, section_data in data.items():
            tab = SectionTab(section_name, section_data)
            self.section_tabs[section_name] = tab
            self.tab_widget.addTab(tab, section_name)
    
    def update_tab_indicators(self, data: Dict[str, Any]):
        """Update tab names with status indicators."""
        for i, (section_name, section_data) in enumerate(data.items()):
            status = self.get_section_status(section_data)
            
            if status == "CRITICAL":
                indicator = "●"
                color = QColor("#FF4444")
            elif status == "WARNING":
                indicator = "●"
                color = QColor("#FFAA00")
            else:
                indicator = "●"
                color = QColor("#44AA44")
            
            tab_text = f"{indicator} {section_name}"
            self.tab_widget.setTabText(i, tab_text)
            self.tab_widget.tabBar().setTabTextColor(i, color)
    
    def get_section_status(self, section_data: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
        """Get overall status for a section."""
        has_critical = False
        has_warning = False
        
        for subsection_data in section_data.values():
            for req_data in subsection_data.values():
                current = req_data.get('current_value', 0)
                threshold = req_data.get('threshold', 0)
                warning_threshold = req_data.get('warning_threshold', 0)
                
                # Check if this is an error metric
                error_keywords = [
                    'error', 'failure', 'degradation', 'slip', 'drop', 'variance',
                    'drift', 'diff', 'jump', 'oscillation', 'activity', 'rate', 'anomaly'
                ]
                is_error_metric = any(keyword in req_data['name'].lower() for keyword in error_keywords)
                
                if is_error_metric:
                    if current > threshold:
                        has_critical = True
                    elif current > warning_threshold:
                        has_warning = True
                else:
                    if current < threshold:
                        has_critical = True
                    elif current < warning_threshold:
                        has_warning = True
        
        if has_critical:
            return "CRITICAL"
        elif has_warning:
            return "WARNING"
        else:
            return "OK"
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.update_timer.stop()
        event.accept()


def main():
    """Main function for standalone testing."""
    app = QApplication(sys.argv)
    
    # Create test tracker
    from vehicle_requirements_tracker import VehicleRequirementsTracker
    tracker = VehicleRequirementsTracker()
    
    # Add test vehicles
    for i in range(3):
        vehicle_id = f"Vehicle-{i+1}"
        tracker.add_vehicle(vehicle_id)
    
    # Create and show GUI
    gui = GPSVehicleRequirementsNotificationGUI()
    gui.set_vehicle_tracker(tracker)
    gui.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()