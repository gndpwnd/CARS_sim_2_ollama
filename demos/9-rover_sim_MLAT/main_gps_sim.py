#!/usr/bin/env python3
"""
GPS Localization Simulation - Main Entry Point
Simplified main script that orchestrates the simulation components.
"""

import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import GPSLocalizationGUI

def main():
    """Main entry point for the GPS localization simulation."""
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = GPSLocalizationGUI()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()