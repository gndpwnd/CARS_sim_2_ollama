import json
import sys
import threading
import time
from typing import Dict, Any
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QScrollArea, QGridLayout, QFrame, QTabWidget
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from run_sim import GPSRequirementsSimulator


class DataUpdateWorker(QThread):
    """Worker thread to handle data updates from the simulation."""
    
    data_updated = pyqtSignal(dict)
    
    def __init__(self, simulator: GPSRequirementsSimulator):
        super().__init__()
        self.simulator = simulator
        self.is_running = True
    
    def run(self):
        """Main worker thread loop."""
        while self.is_running:
            try:
                data = self.simulator.get_latest_data()
                if data:
                    self.data_updated.emit(data)
                time.sleep(0.5)
            except Exception as e:
                print(f"Error in data update worker: {e}")
                time.sleep(1.0)
    
    def stop(self):
        """Stop the worker thread."""
        self.is_running = False
        self.quit()
        self.wait()


class RequirementIndicator(QFrame):
    """Individual requirement indicator that shows status with color coding."""
    
    def __init__(self, name: str, requirement_data: Dict[str, Any]):
        super().__init__()
        self.name = name
        self.requirement_data = requirement_data.copy()
        self.setup_ui()
        self.update_status()
    
    def setup_ui(self):
        """Set up the UI for the requirement indicator."""
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
        
        # Set fixed size for consistent grid appearance
        self.setFixedSize(140, 80)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(2)
    
    def update_status(self):
        """Update the visual status based on current values."""
        current = self.requirement_data.get('current_value', 0)
        threshold = self.requirement_data.get('threshold', 0)
        warning_threshold = self.requirement_data.get('warning_threshold', 0)
        unit = self.requirement_data.get('unit', '')
        
        # Update value display
        self.value_label.setText(f"{current:.2f} {unit}")
        
        # Determine status and color
        if self._is_requirement_met(current, threshold, warning_threshold):
            status = "OK"
            color = "#4CAF50"  # Green
            text_color = "#FFFFFF"
        elif self._is_in_warning_range(current, threshold, warning_threshold):
            status = "WARNING"
            color = "#FF9800"  # Orange
            text_color = "#000000"
        else:
            status = "CRITICAL"
            color = "#F44336"  # Red
            text_color = "#FFFFFF"
        
        self.status_label.setText(status)
        
        # Set colors
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
    
    def _is_requirement_met(self, current: float, threshold: float, warning_threshold: float) -> bool:
        """Determine if requirement is met (green status)."""
        error_keywords = [
            'error', 'failure', 'degradation', 'slip', 'drop', 'variance',
            'drift', 'diff', 'jump', 'oscillation', 'activity'
        ]
        
        is_error_metric = any(keyword in self.name.lower() for keyword in error_keywords)
        
        if is_error_metric:
            return current <= warning_threshold
        else:
            return current >= warning_threshold
    
    def _is_in_warning_range(self, current: float, threshold: float, warning_threshold: float) -> bool:
        """Determine if value is in warning range (orange status)."""
        error_keywords = [
            'error', 'failure', 'degradation', 'slip', 'drop', 'variance',
            'drift', 'diff', 'jump', 'oscillation', 'activity'
        ]
        
        is_error_metric = any(keyword in self.name.lower() for keyword in error_keywords)

        if is_error_metric:
            return warning_threshold < current <= threshold
        else:
            return threshold <= current < warning_threshold
    
    def update_requirement_data(self, new_data: Dict[str, Any]):
        """Update the requirement data and refresh display."""
        self.requirement_data.update(new_data)
        self.update_status()


class SubsectionGrid(QWidget):
    """Grid layout for a subsection showing multiple requirement indicators."""
    
    def __init__(self, subsection_name: str, requirements: Dict[str, Dict[str, Any]]):
        super().__init__()
        self.subsection_name = subsection_name
        self.requirements = requirements
        self.indicators = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the subsection grid."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Subsection title
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
        
        # Add requirement indicators to grid
        row, col = 0, 0
        max_cols = 4
        
        for req_name, req_data in self.requirements.items():
            indicator = RequirementIndicator(req_data['name'], req_data)
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
                indicator.update_requirement_data(updated_requirements[req_name])


class SectionTab(QScrollArea):
    """Scrollable tab for a major section containing multiple subsections."""
    
    def __init__(self, section_name: str, section_data: Dict[str, Dict[str, Dict[str, Any]]]):
        super().__init__()
        self.section_name = section_name
        self.section_data = section_data
        self.subsection_grids = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI for the section tab."""
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Main content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add subsection grids
        for subsection_name, subsection_data in self.section_data.items():
            subsection_grid = SubsectionGrid(subsection_name, subsection_data)
            self.subsection_grids[subsection_name] = subsection_grid
            content_layout.addWidget(subsection_grid)
        
        content_layout.addStretch()
        self.setWidget(content_widget)
    
    def update_section(self, updated_section_data: Dict[str, Dict[str, Dict[str, Any]]]):
        """Update all subsections in this section."""
        for subsection_name, subsection_grid in self.subsection_grids.items():
            if subsection_name in updated_section_data:
                subsection_grid.update_indicators(updated_section_data[subsection_name])


class GPSRequirementsNotificationGUI(QMainWindow):
    """Main notification GUI window showing GPS requirements status."""
    
    def __init__(self, config_file: str = "requirements_config.json"):
        super().__init__()
        self.config_file = config_file
        self.requirements_data = self.load_requirements()
        self.section_tabs = {}
        
        # Initialize simulator connection
        self.simulator = GPSRequirementsSimulator(config_file)
        self.data_worker = None
        
        self.setup_ui()
        self.start_data_connection()
    
    def load_requirements(self) -> Dict[str, Any]:
        """Load requirements configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Configuration file {self.config_file} not found!")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON configuration: {e}")
            return {}
    
    def setup_ui(self):
        """Set up the main UI."""
        self.setWindowTitle("GPS Requirements Notification Dashboard")
        self.setGeometry(200, 200, 1200, 800)
        
        # Set dark theme
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
            QTabBar::tab:hover {
                background-color: #4a4a4a;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        self.title_label = QLabel("GPS Denial Detection Requirements Dashboard")
        self.title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: #404040;
                padding: 12px;
                border-radius: 6px;
                border: 2px solid #555555;
                margin-bottom: 10px;
            }
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Connection status
        self.connection_label = QLabel("Status: Connecting...")
        self.connection_label.setStyleSheet("""
            QLabel {
                color: #FFAA00;
                background-color: #333333;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.connection_label)
        
        # Tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs for each major section
        self.create_section_tabs()
        
        # Control buttons
        self.create_control_buttons(layout)
        
        # Status timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_connection_status)
        self.status_timer.start(1000)
    
    def create_section_tabs(self):
        """Create tabs for each major section."""
        for section_name, section_data in self.requirements_data.items():
            section_tab = SectionTab(section_name, section_data)
            self.section_tabs[section_name] = section_tab
            self.tab_widget.addTab(section_tab, section_name)
        
        self.update_tab_status_indicators()
    
    def create_control_buttons(self, layout: QVBoxLayout):
        """Create control buttons."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        button_style = """
            QPushButton {
                min-width: 100px;
                min-height: 35px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                border: 2px solid #333;
                color: #FFFFFF;
                background-color: #555555;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """
        
        self.connect_btn = QPushButton("Disconnect")
        self.connect_btn.setStyleSheet(button_style)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addStretch()
        
        layout.addWidget(button_widget)
    
    def start_data_connection(self):
        """Start the data connection to the simulator."""
        try:
            if not self.simulator.is_running:
                self.simulator.start_simulation()
            
            self.data_worker = DataUpdateWorker(self.simulator)
            self.data_worker.data_updated.connect(self.handle_data_update)
            self.data_worker.start()
            
            print("Data connection established")
            
        except Exception as e:
            print(f"Failed to establish data connection: {e}")
    
    def stop_data_connection(self):
        """Stop the data connection."""
        if self.data_worker:
            self.data_worker.stop()
            self.data_worker = None
        
        if self.simulator.is_running:
            self.simulator.stop_simulation()
        
        print("Data connection stopped")
    
    def handle_data_update(self, data: Dict[str, Any]):
        """Handle incoming data updates from the simulator."""
        for section_name, section_tab in self.section_tabs.items():
            if section_name in data:
                section_tab.update_section(data[section_name])
        
        self.update_tab_status_indicators()
    
    def update_connection_status(self):
        """Update the connection status display."""
        if self.simulator and self.simulator.is_running:
            status_info = self.simulator.get_simulation_status()
            
            status_text = f"Connected | Time: {status_info['simulation_time']:.1f}s | Scenario: {status_info['current_scenario']}"
            self.connection_label.setText(f"Status: {status_text}")
            self.connection_label.setStyleSheet("""
                QLabel {
                    color: #44AA44;
                    background-color: #333333;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-weight: bold;
                }
            """)
            
        else:
            self.connection_label.setText("Status: Disconnected")
            self.connection_label.setStyleSheet("""
                QLabel {
                    color: #FF4444;
                    background-color: #333333;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-weight: bold;
                }
            """)
    
    def toggle_connection(self):
        """Toggle the data connection."""
        if self.simulator and self.simulator.is_running:
            self.stop_data_connection()
            self.connect_btn.setText("Connect")
        else:
            self.start_data_connection()
            self.connect_btn.setText("Disconnect")
    
    def get_section_status(self, section_name: str) -> str:
        """Get the overall status of a section."""
        if section_name not in self.requirements_data:
            return "OK"
        
        has_critical = False
        has_warning = False
        
        section_data = self.requirements_data[section_name]
        for subsection_name, subsection_data in section_data.items():
            for req_name, req_data in subsection_data.items():
                current = req_data.get('current_value', 0)
                threshold = req_data.get('threshold', 0)
                warning_threshold = req_data.get('warning_threshold', 0)
                
                error_keywords = [
                    'error', 'failure', 'degradation', 'slip', 'drop', 'variance',
                    'drift', 'diff', 'jump', 'oscillation', 'activity'
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
    
    def update_tab_status_indicators(self):
        """Update the tab text with status indicators."""
        for i in range(self.tab_widget.count()):
            section_name = list(self.section_tabs.keys())[i]
            status = self.get_section_status(section_name)
            
            if status == "CRITICAL":
                tab_text = f"● {section_name}"
                self.tab_widget.tabBar().setTabTextColor(i, QColor("#FF4444"))
            elif status == "WARNING":
                tab_text = f"● {section_name}"
                self.tab_widget.tabBar().setTabTextColor(i, QColor("#FFAA00"))
            else:
                tab_text = f"● {section_name}"
                self.tab_widget.tabBar().setTabTextColor(i, QColor("#44AA44"))
            
            self.tab_widget.setTabText(i, tab_text)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.stop_data_connection()
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        event.accept()


def main():
    """Main function to run the notification GUI."""
    app = QApplication(sys.argv)
    notification_gui = GPSRequirementsNotificationGUI()
    notification_gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()