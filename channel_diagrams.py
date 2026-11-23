
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np


def draw_channel(
    shape,
    depth,
    bottom_width=None,
    side_slope=None,
    right_side_slope=None,
    diameter=None
):
    """Draw an open-channel cross-section."""

    if depth <= 0:
        raise ValueError("Water depth must be positive.")

    left_slope = side_slope
    right_slope = (
        right_side_slope
        if right_side_slope is not None
        else side_slope
    )

    fig, ax = plt.subplots(figsize=(8, 5))

    water_color = "#55B8E8"
    channel_color = "#34495E"

    if shape == "rectangular":
        if bottom_width is None or bottom_width <= 0:
            raise ValueError("Bottom width must be positive.")

        ax.plot(
            [0, bottom_width, bottom_width, 0, 0],
            [0, 0, depth, depth, 0],
            color=channel_color, linewidth=3
        )

        ax.fill_between(
            [0, bottom_width], 0, depth,
            color=water_color, alpha=0.45
        )

        ax.plot(
            [0, bottom_width], [depth, depth],
            color="#087EBD", linewidth=2
        )

        ax.annotate(
            f"b = {bottom_width:.2f} m",
            (bottom_width / 2, -0.12),
            ha="center"
        )

    elif shape == "trapezoidal":
        if bottom_width is None or bottom_width <= 0:
            raise ValueError("Bottom width must be positive.")

        if left_slope is None or left_slope < 0:
            raise ValueError("Invalid left side slope.")

        if right_slope is None or right_slope < 0:
            raise ValueError("Invalid right side slope.")

        left_x = -left_slope * depth
        right_x = bottom_width + right_slope * depth

        ax.plot(
            [left_x, 0, bottom_width, right_x],
            [depth, 0, 0, depth],
            color=channel_color, linewidth=3
        )

        ax.fill(
            [left_x, right_x, bottom_width, 0],
            [depth, depth, 0, 0],
            color=water_color, alpha=0.45
        )

        ax.plot(
            [left_x, right_x], [depth, depth],
            color="#087EBD", linewidth=2
        )

    elif shape == "triangular":
        if left_slope is None or left_slope < 0:
            raise ValueError("Invalid left side slope.")

        if right_slope is None or right_slope < 0:
            raise ValueError("Invalid right side slope.")

        if left_slope + right_slope <= 0:
            raise ValueError("At least one side slope must be greater than zero.")

        left_x = -left_slope * depth
        right_x = right_slope * depth

        ax.plot(
            [left_x, 0, right_x],
            [depth, 0, depth],
            color=channel_color, linewidth=3
        )

        ax.fill(
            [left_x, 0, right_x],
            [depth, 0, depth],
            color=water_color, alpha=0.45
        )

        ax.plot(
            [left_x, right_x], [depth, depth],
            color="#087EBD", linewidth=2
        )

    elif shape == "circular":
        if diameter is None or diameter <= 0:
            raise ValueError("Diameter must be positive.")

        if depth > diameter * (1 + 1e-9):
            raise ValueError("Depth cannot exceed the diameter.")

        radius = diameter / 2

        circle = Circle(
            (0, radius), radius,
            fill=False, color=channel_color, linewidth=3
        )
        ax.add_patch(circle)

        if depth >= diameter * (1 - 1e-9):
            # Pipe flowing full: the whole circle is water.
            ax.add_patch(Circle(
                (0, radius), radius,
                color=water_color, alpha=0.45
            ))
            ax.autoscale_view()
        else:
            half_chord = np.sqrt(
                radius**2 - (depth - radius)**2
            )

            x = np.linspace(-half_chord, half_chord, 200)
            y = radius - np.sqrt(radius**2 - x**2)

            ax.fill_between(
                x, y, depth,
                color=water_color, alpha=0.45
            )

            ax.plot(
                [-half_chord, half_chord],
                [depth, depth],
                color="#087EBD", linewidth=2
            )
            ax.autoscale_view()

    else:
        raise ValueError("Unsupported channel shape.")

    ax.set_title(
        f"{shape.capitalize()} Channel Cross-Section",
        fontsize=14, fontweight="bold"
    )

    ax.set_xlabel("Horizontal distance (m)")
    ax.set_ylabel("Elevation (m)")
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(0.15)

    plt.tight_layout()

    return fig
