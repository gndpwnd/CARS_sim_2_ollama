"""
Plotting logic for the GUI with Satellite Visualization
Enhanced version that includes GPS satellite orbital display
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from core.config import X_RANGE, Y_RANGE, MISSION_END
import numpy as np

class PlotManager:
    """Manages matplotlib plotting for the simulation with satellite support"""
    
    def __init__(self, parent):
        """
        Initialize plot manager.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.canvas = FigureCanvasQTAgg(self.fig)
        
        # Satellite visualization settings
        self.show_satellites = True
        self.show_orbit_circle = True
        self.show_satellite_labels = False
        self.satellite_size = 30
        
        # Color mapping for constellations
        self.constellation_colors = {
            'GPS': '#00ff00',      # Green
            'GLONASS': '#ff6600',  # Orange
            'Galileo': '#0099ff'   # Blue
        }
    
    def get_canvas(self):
        """Get the matplotlib canvas widget"""
        return self.canvas
    
    def update_plot(self):
        """Update the matplotlib plot with current simulation state"""
        try:
            self.ax.clear()
            
            # Calculate plot limits (account for satellites if present)
            x_min, x_max, y_min, y_max = self._calculate_plot_limits()
            
            # Set plot limits and style
            self.ax.set_xlim(x_min, x_max)
            self.ax.set_ylim(y_min, y_max)
            self.ax.set_aspect('equal')
            self.ax.grid(True, alpha=0.3)
            
            # Plot satellites first (background layer)
            if self.show_satellites and hasattr(self.parent, 'satellite_constellation'):
                self._plot_satellites()
            
            # Draw jamming zones
            self._draw_jamming_zones()
            
            # Draw mission endpoint
            self._draw_mission_endpoint()
            
            # Draw agents (foreground layer)
            self._draw_agents()
            
            # Draw origin marker
            self.ax.scatter(0, 0, c='black', marker='+', s=100, 
                          linewidths=2, label='Origin', zorder=4)
            
            # Set title with satellite count
            title = f'Multi-Agent GPS Simulation - Iteration {self.parent.iteration_count}'
            if hasattr(self.parent, 'satellite_constellation') and self.parent.satellite_constellation:
                sat_count = len(self.parent.satellite_constellation.satellites)
                title += f' | {sat_count} Satellites Active'
            self.ax.set_title(title, fontsize=12, fontweight='bold')
            
            # Labels
            self.ax.set_xlabel('X Position (Simulation Units)', fontsize=10)
            self.ax.set_ylabel('Y Position (Simulation Units)', fontsize=10)
            
            # Add legend
            self.ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
            
            # Redraw canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"[PLOT] Error updating plot: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_plot_limits(self):
        """Calculate plot limits to accommodate agents and satellites"""
        x_min, x_max = X_RANGE
        y_min, y_max = Y_RANGE
        
        # Expand limits if satellites are present
        if hasattr(self.parent, 'satellite_constellation') and self.parent.satellite_constellation:
            orbit_radius = self.parent.satellite_constellation.orbit_radius
            padding = 1.0
            
            x_min = min(x_min, -orbit_radius - padding)
            x_max = max(x_max, orbit_radius + padding)
            y_min = min(y_min, -orbit_radius - padding)
            y_max = max(y_max, orbit_radius + padding)
        
        return x_min, x_max, y_min, y_max
    
    def _plot_satellites(self):
        """Plot GPS satellite constellation with orbital paths"""
        if not hasattr(self.parent, 'satellite_constellation'):
            return
        
        constellation = self.parent.satellite_constellation
        
        # Update satellite positions
        constellation.update()
        
        # Plot orbit circle (dotted line)
        if self.show_orbit_circle:
            orbit_points = constellation.get_orbit_circle_points()
            orbit_x = [p[0] for p in orbit_points]
            orbit_y = [p[1] for p in orbit_points]
            self.ax.plot(orbit_x, orbit_y, 'k:', alpha=0.3, linewidth=1,
                        label='Satellite Orbit', zorder=1)
        
        # Get satellite positions by constellation
        positions = constellation.get_all_positions()
        
        # Plot each constellation with different colors
        for const_name, const_positions in positions.items():
            if not const_positions:
                continue
            
            sat_x = [p[0] for p in const_positions]
            sat_y = [p[1] for p in const_positions]
            
            color = self.constellation_colors.get(const_name, '#ffffff')
            
            # Plot satellites as triangles
            self.ax.scatter(sat_x, sat_y,
                          c=color,
                          marker='^',
                          s=self.satellite_size,
                          edgecolors='black',
                          linewidths=0.5,
                          alpha=0.8,
                          label=f'{const_name} ({len(const_positions)})',
                          zorder=2)
        
        # Optional: Label satellites (first few only to avoid clutter)
        if self.show_satellite_labels:
            labeled_count = 0
            for sat in constellation.satellites:
                if labeled_count >= 10:  # Limit to 10 labels
                    break
                x, y = sat.get_position()
                direction = "↻" if sat.angular_velocity > 0 else "↺"
                self.ax.text(x + 0.3, y + 0.3, f'{direction}S{sat.prn}',
                           fontsize=6, alpha=0.6, zorder=2)
                labeled_count += 1
    
    def _draw_jamming_zones(self):
        """Draw all jamming zones on the plot"""
        for cx, cy, radius in self.parent.jamming_zones:
            jamming_circle = patches.Circle(
                (cx, cy), radius, 
                color='red', alpha=0.2, linestyle='--', 
                fill=True, label='Jamming Zone', zorder=3
            )
            self.ax.add_patch(jamming_circle)
            
            # Add label
            self.ax.text(cx, cy, f'JAMMING\nR={radius:.1f}', 
                       fontsize=8, ha='center', va='center',
                       color='red', weight='bold', alpha=0.7, zorder=3)
    
    def _draw_mission_endpoint(self):
        """Draw the mission endpoint"""
        self.ax.scatter(
            MISSION_END[0], MISSION_END[1], 
            c='green', marker='*', s=300,
            edgecolors='darkgreen', linewidths=2,
            label='Mission Endpoint', zorder=10
        )
    
    def _draw_agents(self):
        """Draw all agents with their paths and current positions"""
        for agent_id in self.parent.swarm_pos_dict:
            positions = self.parent.swarm_pos_dict[agent_id]
            
            # Draw path history
            xs = [pos[0] for pos in positions]
            ys = [pos[1] for pos in positions]
            self.ax.plot(xs, ys, 'b-', alpha=0.3, linewidth=1, zorder=4)
            
            # Draw current position
            current = positions[-1]
            is_jammed = self.parent.jammed_positions[agent_id]
            color = 'red' if is_jammed else 'blue'
            marker = 'X' if is_jammed else 'o'
            
            self.ax.scatter(current[0], current[1], 
                          c=color, marker=marker, s=100,
                          edgecolors='black', linewidths=1.5, zorder=5)
            
            # Add label with agent info
            label_text = self._get_agent_label(agent_id, current)
            self.ax.text(
                current[0] + 0.3, current[1] + 0.3, label_text, 
                fontsize=8, ha='left', va='bottom',
                bbox=dict(boxstyle='round,pad=0.3', 
                         facecolor='yellow' if is_jammed else 'lightblue',
                         alpha=0.7, edgecolor='black'),
                zorder=5
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
            label_text += f"\nFix: {gps.fix_quality}"
        
        # Add visible satellite count if constellation exists
        if hasattr(self.parent, 'satellite_constellation') and self.parent.satellite_constellation:
            pos = (current_position[0], current_position[1])
            visible_sats = self.parent.satellite_constellation.get_visible_satellites(pos)
            label_text += f"\nVis: {len(visible_sats)}"
        
        return label_text
    
    # Satellite control methods
    
    def toggle_satellites(self):
        """Toggle satellite visibility"""
        self.show_satellites = not self.show_satellites
        status = "visible" if self.show_satellites else "hidden"
        print(f"[PLOT] Satellites: {status}")
        self.update_plot()
    
    def toggle_orbit_circle(self):
        """Toggle orbit circle visibility"""
        self.show_orbit_circle = not self.show_orbit_circle
        status = "visible" if self.show_orbit_circle else "hidden"
        print(f"[PLOT] Orbit circle: {status}")
        self.update_plot()
    
    def toggle_satellite_labels(self):
        """Toggle satellite label visibility"""
        self.show_satellite_labels = not self.show_satellite_labels
        status = "visible" if self.show_satellite_labels else "hidden"
        print(f"[PLOT] Satellite labels: {status}")
        self.update_plot()
    
    def get_satellite_at_position(self, x, y, tolerance=0.5):
        """
        Get satellite information at clicked position
        
        Args:
            x: X coordinate
            y: Y coordinate
            tolerance: Click tolerance radius
            
        Returns:
            Satellite info dict or None
        """
        if not hasattr(self.parent, 'satellite_constellation'):
            return None
        
        constellation = self.parent.satellite_constellation
        
        for sat in constellation.satellites:
            sat_x, sat_y = sat.get_position()
            distance = np.sqrt((sat_x - x)**2 + (sat_y - y)**2)
            
            if distance <= tolerance:
                direction = "Counterclockwise ↻" if sat.angular_velocity > 0 else "Clockwise ↺"
                return {
                    'prn': sat.prn,
                    'constellation': sat.constellation,
                    'position': (sat_x, sat_y),
                    'angle_deg': np.degrees(sat.angle),
                    'direction': direction,
                    'speed': abs(sat.angular_velocity)
                }
        
        return None