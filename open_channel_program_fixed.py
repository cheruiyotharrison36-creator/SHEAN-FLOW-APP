# open_channel_program_fixed.py
# Flow in Non-Erodible Open Channels
# Corrected and validated version of the original command-line program.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_PLOT = True
except ImportError:
    HAVE_PLOT = False

G = 9.81
LINE = "=" * 62


def _finite_positive(value: float, label: str) -> float:
    """Return a finite positive value or raise a useful error."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return value


def _finite_nonnegative(value: float, label: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def _check_depth(y: float) -> float:
    y = _finite_positive(y, "Flow depth y")
    return y


def _bisect_root(function, low: float, high: float, *, tol=1e-9, max_iter=250,
                 label="solution") -> float:
    """Bisection with bracket validation and finite-value checks."""
    low = _finite_positive(low, "Lower depth limit")
    high = _finite_positive(high, "Upper depth limit")
    if high <= low:
        raise ValueError("Upper depth limit must be greater than lower depth limit.")
    if tol <= 0 or not math.isfinite(tol):
        raise ValueError("Tolerance must be a finite positive number.")

    f_low = function(low)
    f_high = function(high)
    if not math.isfinite(f_low) or not math.isfinite(f_high):
        raise ValueError(f"Could not evaluate the {label} at the selected depth limits.")
    if abs(f_low) <= tol:
        return low
    if abs(f_high) <= tol:
        return high
    if f_low * f_high > 0:
        raise ValueError(
            f"Could not bracket the {label}. Try a different discharge or depth range."
        )

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = function(mid)
        if not math.isfinite(f_mid):
            raise ValueError(f"A non-finite value occurred while finding the {label}.")
        if abs(f_mid) <= tol or (high - low) <= tol:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


def _find_first_bracket(function, low: float, high: float, samples=500):
    """Find the first sign change while scanning from shallow to deeper flow.

    This is useful for circular conduits, whose Manning discharge can reach a
    maximum and then decrease as the pipe approaches full depth.
    """
    low = _finite_positive(low, "Lower depth limit")
    high = _finite_positive(high, "Upper depth limit")
    if high <= low:
        raise ValueError("The available depth range is too small for this calculation.")

    # Logarithmic spacing resolves the rapid changes at very shallow depths.
    ratio = (high / low) ** (1.0 / (samples - 1))
    x_previous = low
    f_previous = function(x_previous)
    for i in range(1, samples):
        x = low * ratio ** i
        f_value = function(x)
        if not math.isfinite(f_value):
            continue
        if f_previous == 0 or f_previous * f_value < 0:
            return x_previous, x
        x_previous, f_previous = x, f_value
    raise ValueError("No physically valid solution was found in the available depth range.")


class Channel(ABC):
    name: str = "Channel"

    @abstractmethod
    def area(self, y: float) -> float:
        raise NotImplementedError

    @abstractmethod
    def wetted_perimeter(self, y: float) -> float:
        raise NotImplementedError

    @abstractmethod
    def top_width(self, y: float) -> float:
        raise NotImplementedError

    def hydraulic_radius(self, y: float) -> float:
        y = _check_depth(y)
        perimeter = self.wetted_perimeter(y)
        area = self.area(y)
        if perimeter <= 0 or area <= 0:
            raise ValueError("Hydraulic radius is undefined at this flow depth.")
        return area / perimeter

    def properties(self, y: float) -> dict:
        y = _check_depth(y)
        area = self.area(y)
        perimeter = self.wetted_perimeter(y)
        top_width = self.top_width(y)
        if area <= 0 or perimeter <= 0:
            raise ValueError("Channel properties are undefined at this flow depth.")
        return {
            "y": y,
            "A": area,
            "P": perimeter,
            "B": top_width,
            "R": area / perimeter,
            "D_h": area / top_width if top_width > 0 else math.nan,
        }


@dataclass
class RectangularChannel(Channel):
    b: float
    name: str = "Rectangular"

    def __post_init__(self):
        self.b = _finite_positive(self.b, "Bottom width b")

    def area(self, y):
        y = _check_depth(y)
        return self.b * y

    def wetted_perimeter(self, y):
        y = _check_depth(y)
        return self.b + 2.0 * y

    def top_width(self, y):
        _check_depth(y)
        return self.b


@dataclass
class TrapezoidalChannel(Channel):
    b: float
    m: float
    n: float
    name: str = "Trapezoidal"

    def __post_init__(self):
        self.b = _finite_positive(self.b, "Bottom width b")
        self.m = _finite_nonnegative(self.m, "Left side slope m")
        self.n = _finite_nonnegative(self.n, "Right side slope n")
        if self.m + self.n <= 0:
            raise ValueError("At least one side slope must be greater than zero.")

    def area(self, y):
        y = _check_depth(y)
        return self.b * y + 0.5 * (self.m + self.n) * y ** 2

    def wetted_perimeter(self, y):
        y = _check_depth(y)
        return self.b + y * math.sqrt(1 + self.m ** 2) + y * math.sqrt(1 + self.n ** 2)

    def top_width(self, y):
        y = _check_depth(y)
        return self.b + (self.m + self.n) * y


@dataclass
class TriangularChannel(Channel):
    m: float
    n: float
    name: str = "Triangular"

    def __post_init__(self):
        self.m = _finite_nonnegative(self.m, "Left side slope m")
        self.n = _finite_nonnegative(self.n, "Right side slope n")
        if self.m + self.n <= 0:
            raise ValueError("At least one side slope must be greater than zero.")

    def area(self, y):
        y = _check_depth(y)
        return 0.5 * (self.m + self.n) * y ** 2

    def wetted_perimeter(self, y):
        y = _check_depth(y)
        return y * (math.sqrt(1 + self.m ** 2) + math.sqrt(1 + self.n ** 2))

    def top_width(self, y):
        y = _check_depth(y)
        return (self.m + self.n) * y


@dataclass
class CircularChannel(Channel):
    D: float
    name: str = "Circular"

    def __post_init__(self):
        self.D = _finite_positive(self.D, "Pipe diameter D")

    def _check_circular_depth(self, y):
        y = _check_depth(y)
        if y > self.D:
            raise ValueError("Flow depth in a circular open channel cannot exceed the pipe diameter.")
        return y

    def _theta(self, y):
        y = self._check_circular_depth(y)
        ratio = max(-1.0, min(1.0, 1.0 - 2.0 * y / self.D))
        return 2.0 * math.acos(ratio)

    def area(self, y):
        y = self._check_circular_depth(y)
        if y == self.D:
            return math.pi * self.D ** 2 / 4.0
        theta = self._theta(y)
        return (self.D ** 2 / 8.0) * (theta - math.sin(theta))

    def wetted_perimeter(self, y):
        y = self._check_circular_depth(y)
        return (self.D / 2.0) * self._theta(y)

    def top_width(self, y):
        y = self._check_circular_depth(y)
        if y == self.D:
            return 0.0
        return self.D * math.sin(self._theta(y) / 2.0)


MANNINGS_N = {
    "Planed wood": 0.012,
    "Unplaned wood": 0.013,
    "Finished concrete": 0.012,
    "Unfinished concrete": 0.014,
    "Sewer pipe": 0.013,
    "Brick": 0.016,
    "Cast iron, wrought iron": 0.015,
    "Concrete pipe": 0.015,
    "Riveted steel": 0.017,
    "Earth, straight": 0.022,
    "Corrugated metal flumes": 0.025,
    "Rubble": 0.030,
    "Earth with stones and weeds": 0.035,
    "Mountain streams": 0.050,
}


class Manning:
    @staticmethod
    def _validate(n, S0):
        n = _finite_positive(n, "Manning roughness coefficient n")
        S0 = _finite_positive(S0, "Bed slope S0")
        return n, S0

    @staticmethod
    def discharge(channel, y, n, S0):
        y = _check_depth(y)
        n, S0 = Manning._validate(n, S0)
        area = channel.area(y)
        radius = channel.hydraulic_radius(y)
        return (1.0 / n) * area * radius ** (2.0 / 3.0) * math.sqrt(S0)

    @staticmethod
    def velocity(channel, y, n, S0):
        y = _check_depth(y)
        n, S0 = Manning._validate(n, S0)
        radius = channel.hydraulic_radius(y)
        return (1.0 / n) * radius ** (2.0 / 3.0) * math.sqrt(S0)

    @staticmethod
    def normal_depth(channel, Q, n, S0, y_low=1e-7, y_high=None, tol=1e-9, max_iter=250):
        Q = _finite_positive(Q, "Discharge Q")
        n, S0 = Manning._validate(n, S0)
        low = _finite_positive(y_low, "Lower depth limit")
        if y_high is None:
            y_high = channel.D * (1.0 - 1e-10) if isinstance(channel, CircularChannel) else 1000.0
        high = _finite_positive(y_high, "Upper depth limit")
        if isinstance(channel, CircularChannel):
            high = min(high, channel.D * (1.0 - 1e-10))
        function = lambda depth: Manning.discharge(channel, depth, n, S0) - Q
        bracket_low, bracket_high = _find_first_bracket(function, low, high)
        return _bisect_root(function, bracket_low, bracket_high, tol=tol,
                            max_iter=max_iter, label="normal depth")

    @staticmethod
    def discharge_depth_curve(channel, n, S0, y_max, num_points=200):
        n, S0 = Manning._validate(n, S0)
        y_max = _finite_positive(y_max, "Maximum depth")
        if not isinstance(num_points, int) or num_points < 2:
            raise ValueError("Number of curve points must be an integer of at least 2.")
        if isinstance(channel, CircularChannel) and y_max > channel.D:
            raise ValueError("Maximum depth cannot exceed the circular pipe diameter.")
        ys = [y_max * i / (num_points - 1) for i in range(num_points)]
        # The zero-depth point has zero discharge; Manning's equation is evaluated
        # only for positive depths to avoid a zero hydraulic radius.
        Qs = [0.0 if y == 0 else Manning.discharge(channel, y, n, S0) for y in ys]
        return ys, Qs


class CriticalFlow:
    @staticmethod
    def froude_number(channel, y, Q):
        y = _check_depth(y)
        Q = _finite_nonnegative(Q, "Discharge Q")
        area = channel.area(y)
        top_width = channel.top_width(y)
        if area <= 0 or top_width <= 0:
            raise ValueError("Froude number is undefined at this flow depth (check the top width and flow area).")
        hydraulic_depth = area / top_width
        velocity = Q / area
        return velocity / math.sqrt(G * hydraulic_depth)

    @staticmethod
    def specific_energy(channel, y, Q):
        y = _check_depth(y)
        Q = _finite_nonnegative(Q, "Discharge Q")
        area = channel.area(y)
        if area <= 0:
            raise ValueError("Specific energy is undefined because the flow area is zero.")
        return y + Q ** 2 / (2.0 * G * area ** 2)

    @staticmethod
    def critical_depth(channel, Q, y_low=1e-7, y_high=None, tol=1e-9, max_iter=250):
        Q = _finite_positive(Q, "Discharge Q")
        low = _finite_positive(y_low, "Lower depth limit")
        if y_high is None:
            y_high = channel.D * (1.0 - 1e-10) if isinstance(channel, CircularChannel) else 1000.0
        high = _finite_positive(y_high, "Upper depth limit")
        if isinstance(channel, CircularChannel):
            high = min(high, channel.D * (1.0 - 1e-10))

        def function(depth):
            area = channel.area(depth)
            top_width = channel.top_width(depth)
            if area <= 0 or top_width <= 0:
                return math.nan
            return Q ** 2 * top_width / (G * area ** 3) - 1.0

        bracket_low, bracket_high = _find_first_bracket(function, low, high)
        return _bisect_root(function, bracket_low, bracket_high, tol=tol,
                            max_iter=max_iter, label="critical depth")


def prompt_float(message, *, minimum=None, allow_zero=False):
    while True:
        raw = input(message).strip()
        try:
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError
            if allow_zero:
                if value < 0:
                    raise ValueError
            elif value <= 0:
                raise ValueError
            if minimum is not None and value < minimum:
                raise ValueError
            return value
        except ValueError:
            qualifier = "zero or a positive" if allow_zero else "positive"
            print(f"    Please enter a finite {qualifier} number.")


def header(title):
    print("\n" + LINE)
    print(f"{title:^62}")
    print(LINE)


def build_channel():
    while True:
        header("SELECT CHANNEL TYPE")
        print(" [1] Rectangular   [2] Trapezoidal   [3] Triangular   [4] Circular")
        choice = input(" Choice: ").strip()
        try:
            if choice == "1":
                return RectangularChannel(b=prompt_float("   Bottom width b (m): "))
            if choice == "2":
                b = prompt_float("   Bottom width b (m): ")
                m = prompt_float("   Left side slope m (H per V): ", allow_zero=True)
                n = prompt_float("   Right side slope n (H per V): ", allow_zero=True)
                return TrapezoidalChannel(b=b, m=m, n=n)
            if choice == "3":
                m = prompt_float("   Left side slope m (H per V): ", allow_zero=True)
                n = prompt_float("   Right side slope n (H per V): ", allow_zero=True)
                return TriangularChannel(m=m, n=n)
            if choice == "4":
                return CircularChannel(D=prompt_float("   Diameter D (m): "))
            print(" Invalid choice. Please select 1, 2, 3 or 4.")
        except ValueError as error:
            print(f" Invalid channel dimensions: {error}")


def show_geometry(channel):
    y = prompt_float("\n Depth of flow y (m): ")
    p = channel.properties(y)
    header(f"{channel.name.upper()} CHANNEL GEOMETRY  (y = {y} m)")
    print(f" {'Area (A)':<25}: {p['A']:>12.4f} m^2")
    print(f" {'Wetted perimeter (P)':<25}: {p['P']:>12.4f} m")
    print(f" {'Top width (B)':<25}: {p['B']:>12.4f} m")
    print(f" {'Hydraulic radius (R)':<25}: {p['R']:>12.4f} m")
    dh = "undefined" if math.isnan(p['D_h']) else f"{p['D_h']:.4f} m"
    print(f" {'Hydraulic depth (Dh)':<25}: {dh:>12}")


def menu_manning(channel):
    header("MANNING'S ROUGHNESS COEFFICIENT (n) REFERENCE")
    for material, value in MANNINGS_N.items():
        print(f" {material:<30} n = {value}")
    n = prompt_float("\n Manning's n: ")
    S0 = prompt_float(" Bed slope S0 (m/m): ")
    sub = input(" [a] Discharge Q from depth y   [b] Normal depth y0 from Q : ").strip().lower()
    header("MANNING'S EQUATION - RESULT")
    try:
        if sub == "a":
            y = prompt_float(" Depth y (m): ")
            Q = Manning.discharge(channel, y, n, S0)
            velocity = Manning.velocity(channel, y, n, S0)
            print(f" {'Discharge Q':<25}: {Q:>12.4f} m^3/s")
            print(f" {'Velocity v':<25}: {velocity:>12.4f} m/s")
        elif sub == "b":
            Q = prompt_float(" Design discharge Q (m^3/s): ")
            y0 = Manning.normal_depth(channel, Q, n, S0)
            print(f" {'Normal depth y0':<25}: {y0:>12.4f} m")
        else:
            print(" Invalid choice. Select a or b.")
    except ValueError as error:
        print(f" Calculation error: {error}")


def menu_critical(channel):
    Q = prompt_float("\n Discharge Q (m^3/s): ")
    header("CRITICAL FLOW ANALYSIS")
    try:
        yc = CriticalFlow.critical_depth(channel, Q)
        Ec = CriticalFlow.specific_energy(channel, yc, Q)
        print(f" {'Critical depth yc':<25}: {yc:>12.4f} m")
        print(f" {'Minimum specific energy Ec':<25}: {Ec:>12.4f} m")
    except ValueError as error:
        print(f" Critical-depth calculation error: {error}")

    try:
        y = prompt_float("\n Actual flow depth y (m): ")
        Fr = CriticalFlow.froude_number(channel, y, Q)
        energy = CriticalFlow.specific_energy(channel, y, Q)
        regime = "Supercritical" if Fr > 1 + 1e-6 else "Subcritical" if Fr < 1 - 1e-6 else "Critical"
        print(f" {'Froude number Fr':<25}: {Fr:>12.4f}   ({regime})")
        print(f" {'Specific energy E':<25}: {energy:>12.4f} m")
    except ValueError as error:
        print(f" Flow-state calculation error: {error}")


def menu_curve(channel):
    header("DISCHARGE-DEPTH CURVE")
    n = prompt_float(" Manning's n: ")
    S0 = prompt_float(" Bed slope S0 (m/m): ")
    if isinstance(channel, CircularChannel):
        y_max = channel.D
        print(f" Using y_max = pipe diameter D = {y_max} m")
    else:
        y_max = prompt_float(" Maximum depth y_max to plot up to (m): ")

    try:
        ys, Qs = Manning.discharge_depth_curve(channel, n, S0, y_max)
        Q_peak = max(Qs)
        y_peak = ys[Qs.index(Q_peak)]
        print(f"\n {'Points computed':<25}: {len(ys)}")
        print(f" {'Peak sampled discharge':<25}: {Q_peak:>12.4f} m^3/s")
        print(f" {'Depth at peak sampled Q':<25}: {y_peak:>12.4f} m")
        print("\n  y (m)        Q (m^3/s)")
        step = max(1, len(ys) // 10)
        for i in range(0, len(ys), step):
            print(f"  {ys[i]:>8.3f}     {Qs[i]:>10.4f}")
        if not HAVE_PLOT:
            print("\n matplotlib is not installed; numerical results are available, but no plot was saved.")
            return
        filename = input("\n Save plot as (default: discharge_depth_curve.png): ").strip()
        filename = filename or "discharge_depth_curve.png"
        plt.figure(figsize=(7, 5))
        plt.plot(Qs, ys, linewidth=2)
        plt.xlabel("Discharge Q (m³/s)")
        plt.ylabel("Flow depth y (m)")
        plt.title(f"Discharge-Depth Curve - {channel.name} Channel")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(filename, dpi=160)
        plt.close()
        print(f" Plot saved to: {filename}")
    except (ValueError, OSError) as error:
        print(f" Curve-generation error: {error}")


def main_menu():
    header("MAIN MENU")
    print(" [1] Channel geometry             (Part 1)")
    print(" [2] Manning's equation           (Part 2)")
    print(" [3] Critical flow / Froude no.   (Part 2)")
    print(" [4] Discharge-depth curve        (Part 3)")
    print(" [5] Select a new channel")
    print(" [6] Exit")
    return input(" Choice: ").strip()


def main():
    print(LINE)
    print(f"{'FLOW IN NON-ERODIBLE OPEN CHANNELS':^62}")
    print(f"{'Interactive Geometry & Uniform-Flow Design Tool':^62}")
    print(LINE)
    channel = build_channel()
    while True:
        choice = main_menu()
        try:
            if choice == "1":
                show_geometry(channel)
            elif choice == "2":
                menu_manning(channel)
            elif choice == "3":
                menu_critical(channel)
            elif choice == "4":
                menu_curve(channel)
            elif choice == "5":
                channel = build_channel()
            elif choice == "6":
                print("\n Goodbye.\n")
                break
            else:
                print(" Invalid choice, try again.")
        except (ValueError, ZeroDivisionError, OverflowError) as error:
            print(f"\n Input/calculation error: {error}")


if __name__ == "__main__":
    main()
