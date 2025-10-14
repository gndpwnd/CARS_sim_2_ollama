#!/usr/bin/env python3
"""
Quick test to see if PyQt5 GUI displays
"""
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtCore import Qt

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("GUI Test")
window.setGeometry(100, 100, 400, 300)

label = QLabel("If you see this, PyQt5 is working!", window)
label.setAlignment(Qt.AlignCenter)
label.setStyleSheet("font-size: 16px; padding: 20px;")
window.setCentralWidget(label)

print("Showing window...")
window.show()
print("Window shown. If you don't see it, there's a display issue.")

sys.exit(app.exec_())