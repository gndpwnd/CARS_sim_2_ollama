"""
Mouse interaction and drawing handlers for the GUI.
"""
import math
import matplotlib.patches as patches

class InteractionHandler:
    """Handles mouse interactions for drawing jamming zones"""
    
    def __init__(self, parent):
        """
        Initialize interaction handler.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
        self.drawing_area = False
        self.area_start = None
        self.temp_circle = None
    
    def connect_events(self, canvas, ax):
        """
        Connect mouse events to handlers.
        
        Args:
            canvas: Matplotlib canvas
            ax: Matplotlib axes
        """
        canvas.mpl_connect('button_press_event', self.on_mouse_press)
        canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        canvas.mpl_connect('button_release_event', self.on_mouse_release)
    
    def on_mouse_press(self, event):
        """Handle mouse press events"""
        if event.inaxes != self.parent.plot_manager.ax:
            return
        
        if self.parent.drawing_mode == "add_jamming":
            self._start_drawing_jamming(event)
        elif self.parent.drawing_mode == "remove_jamming":
            self._remove_jamming_at_click(event)
    
    def on_mouse_move(self, event):
        """Handle mouse move events"""
        if not self.drawing_area or event.inaxes != self.parent.plot_manager.ax:
            return
        
        if self.parent.drawing_mode == "add_jamming":
            self._update_temporary_circle(event)
    
    def on_mouse_release(self, event):
        """Handle mouse release events"""
        if not self.drawing_area or event.inaxes != self.parent.plot_manager.ax:
            return
        
        if self.parent.drawing_mode == "add_jamming":
            self._finish_drawing_jamming(event)
    
    def _start_drawing_jamming(self, event):
        """Start drawing a new jamming zone"""
        self.drawing_area = True
        self.area_start = (event.xdata, event.ydata)
        print(f"[JAMMING] Started drawing jamming zone at ({event.xdata:.2f}, {event.ydata:.2f})")
    
    def _update_temporary_circle(self, event):
        """Update the temporary circle while dragging"""
        radius = math.sqrt(
            (event.xdata - self.area_start[0])**2 + 
            (event.ydata - self.area_start[1])**2
        )
        
        # Remove old temporary circle
        if self.temp_circle is not None:
            try:
                self.temp_circle.remove()
            except:
                pass
        
        # Draw new temporary circle
        self.temp_circle = patches.Circle(
            self.area_start, radius, 
            color='red', alpha=0.3, linestyle='--', linewidth=2
        )
        self.parent.plot_manager.ax.add_patch(self.temp_circle)
        self.parent.plot_manager.canvas.draw()
    
    def _finish_drawing_jamming(self, event):
        """Finish drawing and add the jamming zone"""
        radius = math.sqrt(
            (event.xdata - self.area_start[0])**2 + 
            (event.ydata - self.area_start[1])**2
        )
        
        if radius >= 0.5:
            self.parent.jamming_zones.append(
                (self.area_start[0], self.area_start[1], radius)
            )
            print(f"[JAMMING] Added jamming zone at ({self.area_start[0]:.2f}, {self.area_start[1]:.2f}) radius {radius:.2f}")
        else:
            print("[JAMMING] Jamming zone too small, ignoring")
        
        # Clean up
        self.drawing_area = False
        self.area_start = None
        if self.temp_circle is not None:
            try:
                self.temp_circle.remove()
            except:
                pass
            self.temp_circle = None
        
        self.parent.plot_manager.update_plot()
    
    def _remove_jamming_at_click(self, event):
        """Remove jamming zone at click location"""
        click_pos = (event.xdata, event.ydata)
        removed = False
        
        for i, (cx, cy, radius) in enumerate(self.parent.jamming_zones):
            dist = math.sqrt((click_pos[0] - cx)**2 + (click_pos[1] - cy)**2)
            if dist <= radius:
                removed_zone = self.parent.jamming_zones.pop(i)
                print(f"[JAMMING] Removed jamming zone at ({cx:.2f}, {cy:.2f}) radius {radius:.2f}")
                self.parent.plot_manager.update_plot()
                removed = True
                break
        
        if not removed:
            print("[JAMMING] No jamming zone at click location")