"""
GUI controls and button handlers.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)
from PyQt5.QtCore import Qt

class ControlPanel:
    """Manages GUI controls and buttons"""
    
    def __init__(self, parent):
        """
        Initialize control panel.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
    
    def setup_ui(self):
        """Setup the main window UI"""
        self.parent.setWindowTitle("Multi-Agent GPS Simulation")
        self.parent.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.parent.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Add header
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Add plot canvas
        main_layout.addWidget(self.parent.plot_manager.get_canvas())
        
        # Add button panel
        button_layout = self._create_button_panel()
        main_layout.addLayout(button_layout)
    
    def _create_header(self):
        """Create header label"""
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
        return header
    
    def _create_button_panel(self):
        """Create button panel layout"""
        button_layout = QHBoxLayout()
        
        # Mode button
        self.parent.mode_button = self._create_mode_button()
        button_layout.addWidget(self.parent.mode_button)
        
        # Dashboard button
        self.parent.dashboard_button = self._create_dashboard_button()
        button_layout.addWidget(self.parent.dashboard_button)
        
        # Pause button
        self.parent.pause_button = self._create_pause_button()
        button_layout.addWidget(self.parent.pause_button)
        
        # Clear button
        self.parent.clear_button = self._create_clear_button()
        button_layout.addWidget(self.parent.clear_button)
        
        button_layout.addStretch()
        
        # Status label
        self.parent.status_label = self._create_status_label()
        button_layout.addWidget(self.parent.status_label)
        
        return button_layout
    
    def _create_mode_button(self):
        """Create mode toggle button"""
        button = QPushButton("Mode: Navigate")
        button.setStyleSheet("""
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
        button.clicked.connect(self.toggle_mode)
        return button
    
    def _create_dashboard_button(self):
        """Create dashboard toggle button"""
        button = QPushButton("Show Dashboard")
        button.setStyleSheet("""
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
        button.clicked.connect(self.toggle_notification_dashboard)
        return button
    
    def _create_pause_button(self):
        """Create pause/resume button"""
        button = QPushButton("Pause")
        button.setStyleSheet("""
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
        button.clicked.connect(self.toggle_pause)
        return button
    
    def _create_clear_button(self):
        """Create clear jamming button"""
        button = QPushButton("Clear All Jamming")
        button.setStyleSheet("""
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
        button.clicked.connect(self.clear_all_jamming)
        return button
    
    def _create_status_label(self):
        """Create status label"""
        label = QLabel("Iteration: 0")
        label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
        """)
        return label
    
    # Button handlers
    
    def toggle_mode(self):
        """Toggle between navigate, add jamming, and remove jamming modes"""
        modes = ["navigate", "add_jamming", "remove_jamming"]
        current_index = modes.index(self.parent.drawing_mode)
        next_index = (current_index + 1) % len(modes)
        self.parent.drawing_mode = modes[next_index]
        
        if self.parent.drawing_mode == "navigate":
            self.parent.mode_button.setText("Mode: Navigate")
            self.parent.mode_button.setStyleSheet("""
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
        elif self.parent.drawing_mode == "add_jamming":
            self.parent.mode_button.setText("Mode: Add Jamming")
            self.parent.mode_button.setStyleSheet("""
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
            self.parent.mode_button.setText("Mode: Remove Jamming")
            self.parent.mode_button.setStyleSheet("""
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
    
    def toggle_notification_dashboard(self):
        """Toggle the PyQt5 notification dashboard"""
        try:
            from notification_dashboard import GPSRequirementsNotificationGUI
            
            if self.parent.notification_gui is None or not self.parent.notification_gui.isVisible():
                print("[PYQT5] Creating notification dashboard...")
                self.parent.notification_gui = GPSRequirementsNotificationGUI(
                    self.parent.requirements_monitor
                )
                self.parent.notification_gui.show()
                self.parent.dashboard_button.setText("Hide Dashboard")
                print("[PYQT5] Notification dashboard opened")
            else:
                self.parent.notification_gui.close()
                self.parent.notification_gui = None
                self.parent.dashboard_button.setText("Show Dashboard")
                print("[PYQT5] Notification dashboard closed")
        except Exception as e:
            print(f"[PYQT5] Error toggling dashboard: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_pause(self):
        """Toggle simulation pause"""
        self.parent.animation_running = not self.parent.animation_running
        if self.parent.animation_running:
            self.parent.pause_button.setText("Pause")
            print("[SIM] Simulation resumed")
        else:
            self.parent.pause_button.setText("Resume")
            print("[SIM] Simulation paused")
    
    def clear_all_jamming(self):
        """Clear all jamming zones"""
        self.parent.jamming_zones.clear()
        print("[JAMMING] Cleared all jamming zones")
        self.parent.plot_manager.update_plot()