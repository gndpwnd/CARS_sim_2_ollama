import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class SimulationPlot:
    def __init__(self, fig, ax):
        self.fig = fig
        self.ax = ax
        self.canvas = FigureCanvas(self.fig)
        self.temp_circle = None

    def setup_plot(self, bounds):
        """Set up the initial plot configuration."""
        self.ax.set_xlim(bounds[0], bounds[1])
        self.ax.set_ylim(bounds[2], bounds[3])
        self.ax.set_xlabel("X Position (m)")
        self.ax.set_ylabel("Y Position (m)")
        self.ax.set_title("GPS Localization Simulation with Trilateration")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect("equal")

    def update_plot(self, vehicles, gps_denied_areas, bounds):
        """Update the matplotlib plot with current simulation state."""
        self.ax.clear()
        self.setup_plot(bounds)

        # Draw GPS-denied areas
        for area_center_x, area_center_y, radius in gps_denied_areas:
            circle = plt.Circle(
                (area_center_x, area_center_y),
                radius,
                color="red",
                alpha=0.3,
                label="GPS-Denied Area",
            )
            self.ax.add_artist(circle)

        # Draw vehicles
        for vehicle in vehicles:
            # Draw trajectory
            if len(vehicle['trajectory']) > 1:
                trajectory_array = np.array(vehicle['trajectory'])
                self.ax.plot(
                    trajectory_array[:, 0],
                    trajectory_array[:, 1],
                    color=vehicle['color'],
                    alpha=0.3,
                    linewidth=1,
                )

            # Draw vehicle current position
            marker_style = "o" if vehicle['has_gps'] else "s"
            marker_size = 8 if vehicle['has_gps'] else 10
            self.ax.scatter(
                *vehicle['position'],
                color=vehicle['color'],
                marker=marker_style,
                s=marker_size**2,
                edgecolor="black",
                linewidth=2,
                zorder=5,
            )

            # Draw estimated position if available
            if vehicle['estimated_position'] and not vehicle['has_gps']:
                self.ax.scatter(
                    *vehicle['estimated_position'],
                    color="lime",
                    marker="*",
                    s=100,
                    edgecolor="darkgreen",
                    linewidth=2,
                    zorder=4,
                    label="Trilateration Estimate",
                )

                # Draw error circle
                error_circle = plt.Circle(
                    vehicle['estimated_position'],
                    vehicle['position_error'],
                    color="lime",
                    alpha=0.2,
                    fill=True,
                )
                self.ax.add_artist(error_circle)

                # Draw line between true and estimated position
                self.ax.plot(
                    [vehicle['position'][0], vehicle['estimated_position'][0]],
                    [vehicle['position'][1], vehicle['estimated_position'][1]],
                    "r--",
                    alpha=0.7,
                    linewidth=1,
                )

            # Add vehicle label
            self.ax.annotate(
                vehicle['id'],
                vehicle['position'],
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color=vehicle['color'],
                fontweight="bold",
            )

        # Add legend
        legend_elements = []
        legend_elements.append(
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor="gray",
                markersize=8,
                label="GPS Available",
                markeredgecolor="black",
            )
        )
        legend_elements.append(
            plt.Line2D(
                [0],
                [0],
                marker="s",
                color="w",
                markerfacecolor="gray",
                markersize=8,
                label="GPS Denied",
                markeredgecolor="black",
            )
        )
        legend_elements.append(
            plt.Line2D(
                [0],
                [0],
                marker="*",
                color="w",
                markerfacecolor="lime",
                markersize=10,
                label="Trilateration Est.",
                markeredgecolor="darkgreen",
            )
        )

        self.ax.legend(handles=legend_elements, loc="upper right")
        self.canvas.draw()

    def draw_temp_circle(self, center, radius):
        """Draw a temporary circle for GPS-denied area preview."""
        if self.temp_circle is not None:
            self.temp_circle.remove()
        
        self.temp_circle = plt.Circle(center, radius, color="red", alpha=0.3)
        self.ax.add_artist(self.temp_circle)
        self.canvas.draw()

    def clear_temp_circle(self):
        """Remove the temporary circle."""
        if self.temp_circle is not None:
            self.temp_circle.remove()
            self.temp_circle = None
            self.canvas.draw()