import sys
from PyQt5.QtWidgets import QApplication

from occlusion_gui import OcclusionDetectionGUI
from occlusion_checker import OcclusionChecker

# Global configuration
SET_3D = False  # Set to True for 3D mode, False for 2D mode

def main():
    app = QApplication(sys.argv)
    
    # Initialize occlusion checker with tighter tolerance for better accuracy
    occlusion_checker = OcclusionChecker(tolerance=0.05, mode_3d=SET_3D)
    
    # Define initial positions
    if SET_3D:
        # 3D positions with Z variance
        initial_drone_positions = [(20, 20, 5), (80, 20, 3), (50, 80, 7)]
        initial_rover_position = (50, 40, 4)
    else:
        # 2D positions (Z=0)
        initial_drone_positions = [(20, 20), (80, 20), (50, 80)]
        initial_rover_position = (50, 40)
    
    simulation_bounds = (0, 100, 0, 100)
    
    # Create and show the GUI
    window = OcclusionDetectionGUI(
        occlusion_checker=occlusion_checker,
        initial_drone_positions=initial_drone_positions,
        initial_rover_position=initial_rover_position,
        simulation_bounds=simulation_bounds,
        mode_3d=SET_3D
    )
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()