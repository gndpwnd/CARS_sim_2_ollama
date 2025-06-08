"""
Control Panel Widget - Contains simulation control buttons.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QWidget

class ControlPanel(QWidget):
    """Widget containing simulation control buttons."""
    
    # Signals for button clicks
    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    clear_areas_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the control panel UI."""
        layout = QHBoxLayout(self)
        
        # Define button style
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
        
        # Create buttons
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(
            button_style + "QPushButton { background-color: #e3f0d8; color: #2d5016; }"
        )
        self.start_button.clicked.connect(self.start_clicked.emit)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(
            button_style + "QPushButton { background-color: #fdf2ca; color: #8b4513; }"
        )
        self.pause_button.clicked.connect(self.pause_clicked.emit)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setStyleSheet(
            button_style + "QPushButton { background-color: #d8e3f0; color: #1e3a8a; }"
        )
        self.reset_button.clicked.connect(self.reset_clicked.emit)
        
        self.clear_areas_button = QPushButton("Clear Areas")
        self.clear_areas_button.setStyleSheet(
            button_style + "QPushButton { background-color: #f9aeae; color: #7f1d1d; }"
        )
        self.clear_areas_button.clicked.connect(self.clear_areas_clicked.emit)
        
        # Add buttons to layout
        layout.addWidget(self.start_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.clear_areas_button)