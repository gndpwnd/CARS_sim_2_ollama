"""
Plotting logic for the GUI.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from core.config import X_RANGE, Y_RANGE, MISSION_END

class PlotManager:
    """Manages matplotlib plotting for the simulation"""
    
    def __init__(self, parent):
        """
        Initialize plot manager.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.canvas = FigureCanvasQTAgg(self.fig)
    
    def get_canvas(self):
        """Get the matplotlib canvas widget"""
        return self.canvas
    
    def update_plot(self):
        """Update the matplotlib plot with current simulation state"""
        try:
            self.ax.clear()
            
            # Set plot limits and style
            self.ax.set_xlim(X_RANGE)
            self.ax.set_ylim(Y_RANGE)
            self.ax.set_aspect('equal')
            self.ax.grid(True, alpha=0.3)
            
            # Draw jamming zones
            self._draw_jamming_zones()
            
            # Draw mission endpoint
            self._draw_mission_endpoint()
            
            # Draw agents
            self._draw_agents()
            
            # Set title
            self.ax.set_title(f'Multi-Agent GPS Simulation - Iteration {self.parent.iteration_count}')
            
            # Add legend
            self.ax.legend(loc='upper left')
            
            # Redraw canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"[PLOT] Error updating plot: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_jamming_zones(self):
        """Draw all jamming zones on the plot"""
        for cx, cy, radius in self.parent.jamming_zones:
            jamming_circle = patches.Circle(
                (cx, cy), radius, 
                color='red', alpha=0.2, label='Jamming Zone'
            )
            self.ax.add_patch(jamming_circle)
            
            # Add radius label
            self.ax.text(cx, cy, f'R={radius:.1f}', 
                       fontsize=8, ha='center', va='center',
                       bbox=dict(boxstyle='round', facecolor='red', alpha=0.3))
    
    def _draw_mission_endpoint(self):
        """Draw the mission endpoint"""
        self.ax.plot(
            MISSION_END[0], MISSION_END[1], 
            'g*', markersize=20, label='Mission End'
        )
    
    def _draw_agents(self):
        """Draw all agents with their paths and current positions"""
        for agent_id in self.parent.swarm_pos_dict:
            positions = self.parent.swarm_pos_dict[agent_id]
            
            # Draw path history
            xs = [pos[0] for pos in positions]
            ys = [pos[1] for pos in positions]
            self.ax.plot(xs, ys, 'b-', alpha=0.3, linewidth=1)
            
            # Draw current position
            current = positions[-1]
            color = 'red' if self.parent.jammed_positions[agent_id] else 'blue'
            self.ax.plot(current[0], current[1], 'o', color=color, markersize=10)
            
            # Add label with agent info
            label_text = self._get_agent_label(agent_id, current)
            self.ax.text(
                current[0], current[1] + 0.5, label_text, 
                fontsize=8, ha='center'
            )
    
    def _get_agent_label(self, agent_id, current_position):
        """
        Generate label text for an agent.
        
        Args:
            agent_id: Agent identifier
            current_position: Current position [x, y, comm_quality]
            
        Returns:
            Label text string
        """
        label_text = f"{agent_id}\nComm: {current_position[2]:.1f}"
        
        # Add GPS info if available
        if hasattr(self.parent, 'gps_data_cache') and agent_id in self.parent.gps_data_cache:
            gps = self.parent.gps_data_cache[agent_id]
            label_text += f"\nSats: {gps.satellite_count}"
        
        return label_text