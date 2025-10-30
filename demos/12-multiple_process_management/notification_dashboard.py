#!/usr/bin/env python3
"""
GPS Requirements Notification Dashboard (PyQt5)

Displays real-time status of the 12 GPS denial detection requirements
for all agents in the simulation. Spawned from matplotlib simulation window.
"""

import sys
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QGridLayout, QFrame, QTabWidget, QPushButton
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QColor


class RequirementIndicator(QFrame):
    """Individual requirement indicator with color-coded status."""
    
    def __init__(self, name: str, requirement_data: Dict[str, Any]):
        super().__init__()
        self.name = name
        self.requirement_data = requirement_data.copy()
        self.setup_ui()
        self.update_status()
    
    def setup_ui(self):
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
    
    def update_status(self):
        current = self.requirement_data.get('current_value', 0)
        threshold = self.requirement_data.get('threshold', 0)
        warning_threshold = self.requirement_data.get('warning_threshold', 0)
        unit = self.requirement_data.get('unit', '')
        
        self.value_label.setText(f"{current:.2f} {unit}")
        
        # Determine status
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
        self.requirement_data.update(new_data)
        self.update_status()


class AgentTab(QScrollArea):
    """Tab showing all requirements for a single agent."""
    
    def __init__(self, agent_id: str, requirements_data: Dict[str, Any]):
        super().__init__()
        self.agent_id = agent_id
        self.requirements_data = requirements_data
        self.indicators = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create sections for each requirement category
        for section_name, section_data in self.requirements_data.items():
            section_widget = self._create_section_widget(section_name, section_data)
            content_layout.addWidget(section_widget)
        
        content_layout.addStretch()
        self.setWidget(content_widget)
    
    def _create_section_widget(self, section_name: str, section_data: Dict[str, Any]) -> QWidget:
        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget)
        section_layout.setSpacing(8)
        
        # Section title
        title_label = QLabel(section_name)
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
        section_layout.addWidget(title_label)
        
        # Grid for subsections
        for subsection_name, subsection_data in section_data.items():
            subsection_widget = self._create_subsection_grid(subsection_name, subsection_data)
            section_layout.addWidget(subsection_widget)
        
        return section_widget
    
    def _create_subsection_grid(self, subsection_name: str, subsection_data: Dict[str, Any]) -> QWidget:
        subsection_widget = QWidget()
        subsection_layout = QVBoxLayout(subsection_widget)
        subsection_layout.setSpacing(4)
        
        # Subsection title
        subtitle_label = QLabel(subsection_name)
        subtitle_label.setFont(QFont("Arial", 10, QFont.Bold))
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #CCCCCC;
                background-color: #444444;
                padding: 6px;
                border-radius: 3px;
            }
        """)
        subsection_layout.addWidget(subtitle_label)
        
        # Grid for indicators
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(8)
        
        row, col = 0, 0
        max_cols = 4
        
        for req_name, req_data in subsection_data.items():
            indicator = RequirementIndicator(req_data['name'], req_data)
            self.indicators[req_name] = indicator
            
            grid_layout.addWidget(indicator, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        subsection_layout.addWidget(grid_widget)
        return subsection_widget
    
    def update_indicators(self, updated_data: Dict[str, Any]):
        """Update all indicators with new data."""
        for section_name, section_data in updated_data.items():
            for subsection_name, subsection_data in section_data.items():
                for req_name, req_data in subsection_data.items():
                    if req_name in self.indicators:
                        self.indicators[req_name].update_requirement_data(req_data)


class GPSRequirementsNotificationGUI(QMainWindow):
    """Main window for GPS requirements notification dashboard."""
    
    def __init__(self, requirements_monitor=None):
        super().__init__()
        self.requirements_monitor = requirements_monitor
        self.agent_tabs = {}
        self.setup_ui()
        self.start_update_timer()
    
    def setup_ui(self):
        """Setup the main window UI"""
        print("[DASHBOARD] Setting up UI...")
        self.setWindowTitle("GPS Requirements Notification Dashboard")
        self.setGeometry(200, 200, 1200, 800)  # Offset from main window
        
        # Force window to front initially
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # Main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header = QLabel("GPS Denial Detection Requirements Monitor")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: #2196F3;
                padding: 15px;
                border-radius: 8px;
            }
        """)
        main_layout.addWidget(header)
        
        # Tab widget for agents
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
                background-color: #FFFFFF;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                color: #333333;
                padding: 10px 20px;
                margin: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #2196F3;
                color: #FFFFFF;
            }
            QTabBar::tab:hover {
                background-color: #BBDEFB;
            }
        """)
        main_layout.addWidget(self.tab_widget)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("Refresh Now")
        refresh_button.clicked.connect(self.update_all_agents)
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(refresh_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
        # Initialize agents
        self.initialize_agents()
    
    def initialize_agents(self):
        """Initialize tabs for all tracked agents."""
        if not self.requirements_monitor:
            print("[DASHBOARD] No requirements monitor provided")
            return
        
        try:
            agent_ids = self.requirements_monitor.get_all_vehicle_ids()
            print(f"[DASHBOARD] Found {len(agent_ids)} agents: {agent_ids}")
            
            for agent_id in agent_ids:
                self.add_agent_tab(agent_id)
                
        except Exception as e:
            print(f"[DASHBOARD] Error initializing agents: {e}")
    
    def add_agent_tab(self, agent_id: str):
        """Add a tab for a specific agent."""
        if agent_id in self.agent_tabs:
            return
        
        if not self.requirements_monitor:
            return
        
        try:
            # Get requirements data for the agent
            req_data = self.requirements_monitor.get_vehicle_requirements_data(agent_id)
            
            if not req_data:
                print(f"[DASHBOARD] No requirements data for {agent_id}")
                return
            
            # Create tab
            agent_tab = AgentTab(agent_id, req_data)
            self.agent_tabs[agent_id] = agent_tab
            
            # Add to tab widget
            self.tab_widget.addTab(agent_tab, agent_id)
            print(f"[DASHBOARD] Added tab for {agent_id}")
            
        except Exception as e:
            print(f"[DASHBOARD] Error adding tab for {agent_id}: {e}")
    
    def update_all_agents(self):
        """Update all agent tabs with latest data."""
        if not self.requirements_monitor:
            return
        
        try:
            for agent_id, agent_tab in self.agent_tabs.items():
                updated_data = self.requirements_monitor.get_vehicle_requirements_data(agent_id)
                if updated_data:
                    agent_tab.update_indicators(updated_data)
        except Exception as e:
            print(f"[DASHBOARD] Error updating agents: {e}")
    
    def start_update_timer(self):
        """Start automatic update timer."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_agents)
        self.update_timer.start(1000)  # Update every second
    
    def closeEvent(self, event):
        """Handle window close event."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        event.accept()


# Standalone test
if __name__ == "__main__":
    from sim_reqs_tracker import create_requirements_monitor
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create requirements monitor
    monitor = create_requirements_monitor()
    
    if monitor:
        # Add test agents
        for i in range(3):
            agent_id = f"agent{i+1}"
            monitor.add_agent(agent_id)
        
        # Create and show GUI
        gui = GPSRequirementsNotificationGUI(monitor)
        gui.show()
        
        sys.exit(app.exec_())
    else:
        print("Failed to create requirements monitor")