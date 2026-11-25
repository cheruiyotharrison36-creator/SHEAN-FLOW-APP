"""
Additional open-channel hydraulics computations.

Pure Python (no Streamlit). Builds on open_channel.py.

Contents
    1. Flow properties: Froude and Reynolds numbers, shear stress, Chezy C
    2. Uniform flow: solve the Chezy-Manning equation for Q, y0, n, S0 or b
    3. Partly full circular pipes
    4. Best hydraulic (most efficient) sections
    5. Specific energy and alternate depth (bisection, Newton, trial and error)
    6. Transitions: bed steps, width changes, reservoir entrance, energy losses
    7. Weirs and flumes
    8. Gradually varied flow: slope classes, profiles, direct step, integration
    9. Discharge-depth-velocity table
"""
from __future__ import annotations

import math

from open_channel import (
    RectangularChannel, TrapezoidalChannel, TriangularChannel, CircularChannel,
    Manning, CriticalFlow, HydraulicJump, G,
    _bisect_root, _finite_positive, _finite_nonnegative,
)

WATER_NU = 1.004e-6      # kinematic viscosity of water at 20 C (m^2/s)
GAMMA_N = 9810.0         # unit weight of water (N/m^3)


# ======================================================================
# 1. FLOW PROPERTIES
# ======================================================================

def regime_from_froude(fr, tol=1e-3):
    if abs(fr - 1.0) <= tol:
        return "Critical"
    return "Subcritical" if fr < 1.0 else "Supercritical"


def reynolds_class(re):
    """Flow state from Re = V R / nu with R the hydraulic radius:
    laminar below 500, transitional up to 2000, turbulent above."""
    if re < 500:
        return "Laminar"
    if re <= 2000:
        return "Transitional"
    return "Turbulent"


def flow_properties(channel, y, Q, n=None, S0=None, nu=WATER_NU):
    """Velocity, Froude number, Reynolds number, shear stress and Chezy C."""
    Q = _finite_positive(Q, "Discharge Q")
    area = channel.area(y)
    perimeter = channel.wetted_perimeter(y)
    top = channel.top_width(y)
    if area <= 0 or perimeter <= 0:
        raise ValueError("The flow area is zero at this depth.")
    radius = area / perimeter
    velocity = Q / area
    hyd_depth = area / top if top > 0 else math.nan
    fr = velocity / math.sqrt(G * hyd_depth) if top > 0 else math.nan
    re = velocity * radius / nu
    out = {
        "A": area, "P": perimeter, "B": top, "R": radius, "V": velocity,
        "hydraulic_depth": hyd_depth, "Fr": fr,
        "regime": regime_from_froude(fr) if math.isfinite(fr) else "—",
        "Re": re, "flow_type": reynolds_class(re),
        "tau0": math.nan, "chezy_C": math.nan,
    }
    if S0 is not None and S0 > 0:
        out["tau0"] = GAMMA_N * radius * S0                  # tau0 = gamma R S0
    if n is not None and n > 0:
        out["chezy_C"] = radius ** (1.0 / 6.0) / n           # C = R^(1/6) / n
    return out


def chezy_from_fanning(f):
    """Chezy C = sqrt(8 g / f) from the Fanning friction factor f."""
    return math.sqrt(8.0 * G / _finite_positive(f, "Friction factor f"))


# ======================================================================
# 2. UNIFORM FLOW: SOLVE FOR ANY ONE UNKNOWN
# ======================================================================

def make_channel(kind, b=None, m1=None, m2=None, D=None):
    if kind == "rectangular":
        return RectangularChannel(b=b)
    if kind == "trapezoidal":
        return TrapezoidalChannel(b=b, m=m1, n=m2)
    if kind == "triangular":
        return TriangularChannel(m=m1, n=m2)
    if kind == "circular":
        return CircularChannel(D=D)
    raise ValueError("Unsupported channel type.")


def channel_kind(channel):
    """Return (kind, parameters) for one of the four channel classes."""
    if isinstance(channel, RectangularChannel):
        return "rectangular", {"b": channel.b}
    if isinstance(channel, TrapezoidalChannel):
        return "trapezoidal", {"b": channel.b, "m1": channel.m, "m2": channel.n}
    if isinstance(channel, TriangularChannel):
        return "triangular", {"m1": channel.m, "m2": channel.n}
    if isinstance(channel, CircularChannel):
        return "circular", {"D": channel.D}
    raise ValueError("Unsupported channel type.")


def slope_from_side_angle(theta_deg):
    """Side slope m (horizontal per 1 vertical) from the side angle measured
    from the horizontal (m = 1 / tan(theta))."""
    theta = _finite_positive(theta_deg, "Side angle")
    if theta >= 90.0:
        raise ValueError("The side angle must be less than 90 degrees.")
    return 1.0 / math.tan(math.radians(theta))


def solve_uniform(kind, unknown, *, Q=None, y=None, n=None, S0=None,
                  b=None, m1=None, m2=None, D=None):
    """Solve Q = (1/n) A R^(2/3) S0^(1/2) for one unknown.

    unknown is one of "Q", "y", "n", "S0", "b".
    Returns a dict with the solved value and the section properties.
    """
    result = {"unknown": unknown}

    def build(width=b):
        return make_channel(kind, b=width, m1=m1, m2=m2, D=D)

    if unknown == "Q":
        channel = build()
        Q = Manning.discharge(channel, _finite_positive(y, "Depth y"), n, S0)
        result["Q"] = Q
    elif unknown == "y":
        channel = build()
        y = Manning.normal_depth(channel, Q, n, S0)
        result["y"] = y
    elif unknown in ("n", "S0"):
        channel = build()
        y = _finite_positive(y, "Depth y")
        Q = _finite_positive(Q, "Discharge Q")
        area = channel.area(y)
        radius = channel.hydraulic_radius(y)
        if unknown == "n":
            S0 = _finite_positive(S0, "Slope S0")
            n = area * radius ** (2.0 / 3.0) * math.sqrt(S0) / Q
            result["n"] = n
        else:
            n = _finite_positive(n, "Manning n")
            S0 = (Q * n / (area * radius ** (2.0 / 3.0))) ** 2
            result["S0"] = S0
    elif unknown == "b":
        if kind not in ("rectangular", "trapezoidal"):
            raise ValueError("Only rectangular and trapezoidal sections have a bottom width.")
        y = _finite_positive(y, "Depth y")
        Q = _finite_positive(Q, "Discharge Q")

        def function(width):
            return Manning.discharge(build(width), y, n, S0) - Q

        low, high = 1e-6, 1.0
        while function(high) < 0:
            high *= 2.0
            if high > 1e6:
                raise ValueError("No bottom width was found for this discharge.")
        b = _bisect_root(function, low, high, label="bottom width")
        channel = build(b)
        result["b"] = b
    else:
        raise ValueError("Unknown quantity to solve for.")

    result["channel"] = channel
    result["props"] = flow_properties(channel, y, Q, n=n, S0=S0)
    result["Q"], result["y"], result["n"], result["S0"] = Q, y, n, S0
    return result


# ======================================================================
# 3. PARTIAL FLOW IN CIRCULAR PIPES
# ======================================================================

def circular_partial_flow(D, y):
    """Ratios of area, hydraulic radius, velocity and discharge to the
    full-pipe values (n and S0 held constant)."""
    D = _finite_positive(D, "Diameter D")
    channel = CircularChannel(D=D)
    area_full = math.pi * D ** 2 / 4.0
    r_full = D / 4.0
    area = channel.area(y)
    radius = channel.hydraulic_radius(y)
    theta = channel._theta(y)
    return {
        "y/D": y / D, "theta_deg": math.degrees(theta),
        "A": area, "A/Af": area / area_full,
        "R/Rf": radius / r_full,
        "V/Vf": (radius / r_full) ** (2.0 / 3.0),
        "Q/Qf": (area / area_full) * (radius / r_full) ** (2.0 / 3.0),
    }


# ======================================================================
# 4. BEST HYDRAULIC (EFFICIENT) SECTIONS
# ======================================================================

def best_section(Q, n, S0, m=None):
    """Most efficient trapezoid for a side slope m (m = 0 gives a rectangle).

    With m = 1/sqrt(3) (60 degree sides) A = sqrt(3) y^2, P = 2 sqrt(3) y and
    R = y/2. In general R = y/2, A = c y^2 with
    c = 2 sqrt(1+m^2) - m and b = 2 y (sqrt(1+m^2) - m).
    """
    Q = _finite_positive(Q, "Discharge Q")
    n = _finite_positive(n, "Manning n")
    S0 = _finite_positive(S0, "Slope S0")
    m = 1.0 / math.sqrt(3.0) if m is None else _finite_nonnegative(m, "Side slope m")
    c = 2.0 * math.sqrt(1.0 + m * m) - m
    y = (Q * n * 2.0 ** (2.0 / 3.0) / (c * math.sqrt(S0))) ** (3.0 / 8.0)
    b = 2.0 * y * (math.sqrt(1.0 + m * m) - m)
    area = c * y * y
    perimeter = 2.0 * c * y
    return {
        "m": m, "side_angle_deg": math.degrees(math.atan(1.0 / m)) if m > 0 else 90.0,
        "y": y, "b": b, "B": b + 2.0 * m * y, "A": area, "P": perimeter,
        "R": area / perimeter, "b_over_y": b / y,
        "V": Q / area,
    }


# ======================================================================
# 5. SPECIFIC ENERGY AND ALTERNATE DEPTH
# ======================================================================

def _y_upper(channel, y_cap=1000.0):
    return channel.D * (1.0 - 1e-10) if isinstance(channel, CircularChannel) else y_cap


def specific_energy_curve(channel, Q, y_max, npts=200):
    """List of (y, E) for constant Q."""
    Q = _finite_positive(Q, "Discharge Q")
    y_max = _finite_positive(y_max, "Maximum depth")
    if isinstance(channel, CircularChannel):
        y_max = min(y_max, channel.D * (1.0 - 1e-10))
    return [
        (y_max * i / npts, CriticalFlow.specific_energy(channel, y_max * i / npts, Q))
        for i in range(1, npts + 1)
    ]


def depth_for_energy(channel, Q, E, branch, tol=1e-10):
    """Depth with specific energy E on the 'sub' or 'super' critical branch."""
    yc = CriticalFlow.critical_depth(channel, Q)
    e_c = CriticalFlow.specific_energy(channel, yc, Q)
    if E < e_c - 1e-12:
        raise ValueError(
            f"E = {E:.4f} m is below the minimum specific energy Ec = {e_c:.4f} m, "
            "so this discharge cannot pass (choked flow)."
        )
    if abs(E - e_c) <= 1e-12:
        return yc

    def function(depth):
        return CriticalFlow.specific_energy(channel, depth, Q) - E

    if branch == "super":
        return _bisect_root(function, 1e-9, yc, tol=tol, label="supercritical depth")
    high = yc
    y_cap = _y_upper(channel)
    while function(high) < 0:
        if high >= y_cap:
            raise ValueError("The subcritical depth would exceed the depth available in this section.")
        high = min(high * 1.5, y_cap)
    return _bisect_root(function, yc, high, tol=tol, label="subcritical depth")


def alternate_depth(channel, Q, y1, method="bisection", y_guess=None,
                    tol=1e-6, max_iter=100):
    """Alternate depth (same E, same Q) with an iteration table.

    method: "bisection", "newton" (safeguarded) or "trial" (tabular trial and error).
    """
    Q = _finite_positive(Q, "Discharge Q")
    y1 = _finite_positive(y1, "Depth y1")
    e1 = CriticalFlow.specific_energy(channel, y1, Q)
    yc = CriticalFlow.critical_depth(channel, Q)
    e_c = CriticalFlow.specific_energy(channel, yc, Q)
    fr1 = CriticalFlow.froude_number(channel, y1, Q)
    sub = y1 > yc

    def f(depth):
        return CriticalFlow.specific_energy(channel, depth, Q) - e1

    info = {"E1": e1, "yc": yc, "Ec": e_c, "Fr1": fr1,
            "branch": "supercritical" if sub else "subcritical"}
    if abs(y1 - yc) < 1e-9:
        info.update(alternate=yc, rows=[], method=method)
        return info

    # bracket for the other branch
    if sub:
        lo, hi = 1e-6, yc
    else:
        lo, hi = yc, yc
        y_cap = _y_upper(channel)
        while f(hi) < 0:
            if hi >= y_cap:
                raise ValueError("The alternate depth would exceed the depth available in this section.")
            hi = min(hi * 1.5, y_cap)

    rows = []
    if method == "bisection":
        a, b = lo, hi
        fa = f(a)
        for i in range(1, max_iter + 1):
            c = 0.5 * (a + b)
            fc = f(c)
            rows.append({"Iteration": i, "a": a, "b": b, "c (midpoint)": c, "f(c) = E(c) − E₁": fc})
            if abs(fc) < tol or 0.5 * (b - a) < tol:
                break
            if fa * fc <= 0:
                b = c
            else:
                a, fa = c, fc
        root = c
    elif method == "newton":
        x = y_guess if y_guess else (0.5 * yc if sub else 2.0 * yc)
        x = min(max(x, lo), hi)
        a, b = lo, hi
        fa = f(a)
        root = x
        for i in range(1, max_iter + 1):
            fx = f(x)
            dfx = 1.0 - CriticalFlow.froude_number(channel, x, Q) ** 2     # dE/dy = 1 - Fr^2
            rows.append({"Iteration": i, "y": x, "f(y)": fx, "f′(y) = 1 − Fr²": dfx})
            root = x
            if abs(fx) < tol:
                break
            if fa * fx <= 0:
                b = x
            else:
                a, fa = x, fx
            x_new = x - fx / dfx if abs(dfx) > 1e-12 else 0.5 * (a + b)
            if not (a < x_new < b):
                x_new = 0.5 * (a + b)      # safeguard: fall back to a bisection step
            if abs(x_new - x) < tol:
                root = x_new
                break
            x = x_new
    elif method == "trial":
        coarse = 0.1 * yc
        fine = 0.01 * yc
        x0 = y_guess if y_guess else (0.5 * yc if sub else 2.0 * yc)
        x0 = min(max(x0, lo), hi)
        direction = 1.0 if f(x0) * f(lo) > 0 else -1.0

        def add_row(depth, value):
            rows.append({"y": depth, "E(y)": value + e1, "E₁ (target)": e1,
                         "E(y) − E₁": value})

        def scan(x, step, first_row_done):
            fx = f(x)
            if not first_row_done:
                add_row(x, fx)
            for _ in range(max_iter):
                x_next = min(max(x + direction * step, lo), hi)
                fn = f(x_next)
                add_row(x_next, fn)
                if fx * fn <= 0:
                    return x, x_next
                if x_next in (lo, hi):
                    break
                x, fx = x_next, fn
            raise ValueError("The trial search did not bracket the alternate depth.")

        a_c, b_c = scan(x0, coarse, False)          # coarse steps
        a_f, b_f = scan(a_c, fine, True)            # fine steps inside that interval
        root = _bisect_root(f, min(a_f, b_f), max(a_f, b_f), tol=1e-10,
                            label="alternate depth")
        add_row(root, f(root))
    else:
        raise ValueError("Unknown method.")

    info.update(alternate=root, rows=rows, method=method)
    return info


# ======================================================================
# 6. TRANSITIONS
# ======================================================================

def transition(ch1, ch2, Q, y1, dz=0.0, ke=0.0, kc=0.0):
    """Energy equation across a transition with a bed rise dz (m) and a
    change of section from ch1 to ch2 (use ch2 = ch1 for a hump alone).

    Losses: h_L = Kc |V2^2 - V1^2| / 2g for a contraction (V2 > V1) or
    Ke |V1^2 - V2^2| / 2g for an expansion.
    """
    Q = _finite_positive(Q, "Discharge Q")
    y1 = _finite_positive(y1, "Depth y1")
    a1 = ch1.area(y1)
    v1 = Q / a1
    e1 = CriticalFlow.specific_energy(ch1, y1, Q)
    fr1 = CriticalFlow.froude_number(ch1, y1, Q)
    yc1 = CriticalFlow.critical_depth(ch1, Q)
    branch = "sub" if y1 > yc1 else "super"
    yc2 = CriticalFlow.critical_depth(ch2, Q)
    ec2 = CriticalFlow.specific_energy(ch2, yc2, Q)

    h_loss = 0.0
    out = {
        "E1": e1, "V1": v1, "Fr1": fr1, "yc2": yc2, "Ec2": ec2,
        "critical_rise": e1 - ec2, "branch": branch,
    }
    for _ in range(100):
        e2 = e1 - dz - h_loss
        if e2 < ec2 - 1e-12:
            # choked: critical depth on the hump, upstream depth rises (damming)
            e1_new = ec2 + dz + h_loss
            y1_new = depth_for_energy(ch1, Q, e1_new, branch)
            out.update(
                choked=True, y2=yc2, E2=ec2, V2=Q / ch2.area(yc2),
                Fr2=1.0, h_loss=h_loss, y1_new=y1_new, E1_new=e1_new,
            )
            return out
        y2 = depth_for_energy(ch2, Q, e2, branch)
        v2 = Q / ch2.area(y2)
        k = kc if v2 > v1 else ke
        new_loss = k * abs(v2 ** 2 - v1 ** 2) / (2.0 * G)
        if abs(new_loss - h_loss) < 1e-12:
            h_loss = new_loss
            break
        h_loss = new_loss
    e2 = e1 - dz - h_loss
    y2 = depth_for_energy(ch2, Q, e2, branch)
    out.update(
        choked=False, y2=y2, E2=e2, V2=Q / ch2.area(y2),
        Fr2=CriticalFlow.froude_number(ch2, y2, Q), h_loss=h_loss,
    )
    return out


def critical_width_rectangular(Q, E):
    """Smallest rectangular width that passes Q with specific energy E:
    q_max = sqrt(g (2E/3)^3)  (maximum discharge at critical depth)."""
    Q = _finite_positive(Q, "Discharge Q")
    E = _finite_positive(E, "Specific energy E")
    return Q / math.sqrt(G * (2.0 * E / 3.0) ** 3)


def entrance_critical(channel, H):
    """Free entrance from a reservoir (V1 = 0): E_c = H, so
    H = y_c + A_c / (2 B_c).  Returns y_c, A_c, B_c and the discharge
    Q = sqrt(g A_c^3 / B_c)."""
    H = _finite_positive(H, "Energy head H")

    def function(depth):
        return depth + channel.area(depth) / (2.0 * channel.top_width(depth)) - H

    hi = _y_upper(channel, y_cap=H)
    hi = min(hi, H)
    yc = _bisect_root(function, 1e-9, hi, label="critical depth")
    a = channel.area(yc)
    b = channel.top_width(yc)
    return {"yc": yc, "A": a, "B": b, "Q": math.sqrt(G * a ** 3 / b)}


# ======================================================================
# 7. WEIRS AND FLUMES
# ======================================================================

SHARP_CREST_METHODS = ("Rehbock", "Kindsvater–Carter", "User-specified")


def effective_crest_length(L, H, end_contractions=0):
    """Francis correction for end contractions: L - 0.1 n H, n = 0, 1 or 2."""
    L = _finite_positive(L, "Crest length")
    H = _finite_positive(H, "Head H")
    if end_contractions not in (0, 1, 2):
        raise ValueError("The number of end contractions must be 0, 1 or 2.")
    length = L - 0.1 * end_contractions * H
    if length <= 0:
        raise ValueError("The effective crest length is not positive.")
    return length


def broad_crested_weir(b, Y, cd=1.0):
    """Q = Cd sqrt(g) (2/3)^(3/2) b Y^(3/2); Cd = 1 for the ideal weir."""
    b = _finite_positive(b, "Crest width b")
    Y = _finite_positive(Y, "Head Y")
    cd = _finite_positive(cd, "Discharge coefficient")
    return cd * math.sqrt(G) * (2.0 / 3.0) ** 1.5 * b * Y ** 1.5


def sharp_crested_cd(Y, P=None, method="Rehbock"):
    """Discharge coefficient of a rectangular thin-plate weir.

    Rehbock:            Cd = 0.611 + 0.075 Y/P
    Kindsvater-Carter:  Cd = 0.602 + 0.075 Y/P  (with the head increased by 1 mm)
    P is the crest height above the approach channel bed; without it the
    Y/P term is dropped (very high weir).
    """
    ratio = Y / P if P else 0.0
    if method == "Rehbock":
        return 0.611 + 0.075 * ratio
    if method.startswith("Kindsvater"):
        return 0.602 + 0.075 * ratio
    raise ValueError("Unknown discharge coefficient method.")


def sharp_crested_weir(b, Y, P=None, method="Rehbock", cd=None, end_contractions=0):
    """Q = (2/3) Cd sqrt(2g) L_eff H^(3/2) for a rectangular thin-plate weir.

    L_eff = b - 0.1 n Y for n end contractions. With the Kindsvater-Carter
    method the head is increased by 0.001 m (SI units). Pass cd to use your
    own coefficient.
    """
    b = _finite_positive(b, "Crest length b")
    Y = _finite_positive(Y, "Head Y")
    head = Y
    if cd is None:
        if method == "User-specified":
            raise ValueError("Enter a discharge coefficient.")
        cd = sharp_crested_cd(Y, P, method)
        if method.startswith("Kindsvater"):
            head = Y + 0.001
    else:
        cd = _finite_positive(cd, "Cd")
    length = effective_crest_length(b, Y, end_contractions)
    return (2.0 / 3.0) * cd * math.sqrt(2.0 * G) * length * head ** 1.5


def v_notch_weir(theta_deg, Y, cd=0.58):
    """Q = (8/15) Cd tan(theta/2) sqrt(2g) Y^(5/2).

    Cd is about 0.58 for a 90 degree notch; it varies with notch angle,
    head and approach geometry."""
    theta = _finite_positive(theta_deg, "Notch angle")
    if theta >= 180.0:
        raise ValueError("The notch angle must be less than 180 degrees.")
    Y = _finite_positive(Y, "Head Y")
    cd = _finite_positive(cd, "Cd")
    return (8.0 / 15.0) * cd * math.tan(math.radians(theta) / 2.0) * math.sqrt(2.0 * G) * Y ** 2.5


def francis_weir(L, H, end_contractions=2):
    """Francis formula in SI units: Q = 1.84 (L - 0.1 n H) H^(3/2),
    with n = 0, 1 or 2 end contractions."""
    length = effective_crest_length(L, H, end_contractions)
    return 1.84 * length * H ** 1.5


def parshall_flume(B_m, H_m):
    """Free-flow Parshall flume: Q = 4 B H^(1.522 B^0.026) with B and H in feet
    and Q in cfs. Inputs and output here are in metres and m^3/s. The formula
    applies to throat widths of about 0.3 m to 2.4 m."""
    B_m = _finite_positive(B_m, "Throat width B")
    H_m = _finite_positive(H_m, "Upstream depth H")
    b_ft, h_ft = B_m / 0.3048, H_m / 0.3048
    q_cfs = 4.0 * b_ft * h_ft ** (1.522 * b_ft ** 0.026)
    return q_cfs * 0.028316846592


def head_for_discharge(function, Q, hi=50.0):
    """Invert any of the weir formulas: find the head Y that gives Q.

    hi is the largest head searched; it is reduced automatically if the
    formula is not valid that high (for example when the effective crest
    length becomes negative)."""
    Q = _finite_positive(Q, "Discharge Q")
    low = 1e-6
    for _ in range(200):
        try:
            q_high = function(hi)
            break
        except ValueError:
            hi *= 0.9
    else:
        raise ValueError("No valid head was found for this weir.")
    if q_high < Q:
        raise ValueError("The discharge is too large for this weir within the valid range of heads.")
    return _bisect_root(lambda Y: function(Y) - Q, low, hi, label="head")


# ======================================================================
# 8. GRADUALLY VARIED FLOW
# ======================================================================

PROFILE_INFO = {
    "M1": ("Backwater", "y > y0 > yc"), "M2": ("Drawdown", "y0 > y > yc"),
    "M3": ("Backwater", "y0 > yc > y"),
    "S1": ("Backwater", "y > yc > y0"), "S2": ("Drawdown", "yc > y > y0"),
    "S3": ("Backwater", "yc > y0 > y"),
    "C1": ("Backwater", "y > yc = y0"), "C3": ("Backwater", "yc = y0 > y"),
    "H2": ("Drawdown", "y > yc"), "H3": ("Backwater", "yc > y"),
    "A2": ("Drawdown", "y > yc"), "A3": ("Backwater", "yc > y"),
}


def critical_slope(channel, Q, n):
    """Slope at which uniform flow is critical: Sc from Manning at y = yc."""
    yc = CriticalFlow.critical_depth(channel, Q)
    area = channel.area(yc)
    radius = channel.hydraulic_radius(yc)
    return (Q * n / (area * radius ** (2.0 / 3.0))) ** 2


def classify_slope(channel, Q, n, S0):
    """Slope class (M, S, C, H or A) with y0, yc and Sc."""
    Q = _finite_positive(Q, "Discharge Q")
    n = _finite_positive(n, "Manning n")
    yc = CriticalFlow.critical_depth(channel, Q)
    sc = critical_slope(channel, Q, n)
    y0 = None
    if S0 < 0:
        kind = "A"
    elif S0 == 0:
        kind = "H"
    else:
        y0 = Manning.normal_depth(channel, Q, n, S0)
        if abs(S0 - sc) <= 1e-6 * sc:
            kind = "C"
        else:
            kind = "M" if S0 < sc else "S"
    names = {"M": "Mild", "S": "Steep", "C": "Critical", "H": "Horizontal", "A": "Adverse"}
    return {"class": kind, "name": names[kind], "y0": y0, "yc": yc, "Sc": sc}


def profile_name(kind, y, y0, yc):
    """Water surface profile label (M1, M2, M3, S1, ..., A3)."""
    if kind == "M":
        return "M1" if y > y0 else ("M2" if y > yc else "M3")
    if kind == "S":
        return "S1" if y > yc else ("S2" if y > y0 else "S3")
    if kind == "C":
        return "C1" if y > yc else "C3"
    if kind in ("H", "A"):
        return f"{kind}2" if y > yc else f"{kind}3"
    raise ValueError("Unknown slope class.")


def friction_slope(channel, y, Q, n):
    area = channel.area(y)
    radius = channel.hydraulic_radius(y)
    return (n * (Q / area) / radius ** (2.0 / 3.0)) ** 2


def gvf_dydx(channel, y, Q, n, S0):
    """dy/dx = (S0 - Sf) / (1 - Fr^2)."""
    fr = CriticalFlow.froude_number(channel, y, Q)
    return (S0 - friction_slope(channel, y, Q, n)) / (1.0 - fr ** 2)


def direct_step(channel, Q, n, S0, y_start, y_end, nsteps=20):
    """Direct step method: dx = (E2 - E1) / (S0 - Sf_mean).

    x is measured in the flow direction from the control section at
    y_start, so computing upstream from a subcritical control gives negative x.
    """
    Q = _finite_positive(Q, "Discharge Q")
    n = _finite_positive(n, "Manning n")
    y_start = _finite_positive(y_start, "Starting depth")
    y_end = _finite_positive(y_end, "Final depth")
    if nsteps < 1 or int(nsteps) != nsteps:
        raise ValueError("Number of steps must be a positive integer.")
    if abs(y_end - y_start) < 1e-12:
        raise ValueError("The starting and final depths must be different.")

    rows = []
    x = 0.0
    prev = None
    for i in range(int(nsteps) + 1):
        y = y_start + (y_end - y_start) * i / nsteps
        area = channel.area(y)
        e = CriticalFlow.specific_energy(channel, y, Q)
        sf = friction_slope(channel, y, Q, n)
        fr = CriticalFlow.froude_number(channel, y, Q)
        dx = 0.0
        sf_mean = math.nan
        if prev is not None:
            sf_mean = 0.5 * (sf + prev["Sf"])
            denom = S0 - sf_mean
            if abs(denom) < 1e-14:
                raise ValueError(
                    "S0 equals the friction slope over this step: the profile "
                    "approaches normal depth asymptotically. Choose a final depth "
                    "slightly different from y0."
                )
            dx = (e - prev["E"]) / denom
            x += dx
        row = {"y": y, "A": area, "V": Q / area, "E": e, "Fr": fr,
               "Sf": sf, "Sf_mean": sf_mean, "dx": dx, "x": x}
        rows.append(row)
        prev = row
    return rows


def rk4_profile(channel, Q, n, S0, y_start, length, nsteps=200):
    """Numerical integration of dy/dx (4th-order Runge-Kutta). length is signed:
    positive downstream, negative upstream. Stops early at critical depth."""
    Q = _finite_positive(Q, "Discharge Q")
    n = _finite_positive(n, "Manning n")
    y = _finite_positive(y_start, "Starting depth")
    h = length / nsteps
    points = [(0.0, y)]
    x = 0.0
    for _ in range(int(nsteps)):
        try:
            k1 = gvf_dydx(channel, y, Q, n, S0)
            k2 = gvf_dydx(channel, y + 0.5 * h * k1, Q, n, S0)
            k3 = gvf_dydx(channel, y + 0.5 * h * k2, Q, n, S0)
            k4 = gvf_dydx(channel, y + h * k3, Q, n, S0)
        except (ValueError, ZeroDivisionError):
            break
        y_new = y + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
        if not math.isfinite(y_new) or y_new <= 1e-6:
            break
        y, x = y_new, x + h
        points.append((x, y))
    return points


def conjugate_from_subcritical(channel, Q, y_sub):
    """Supercritical depth that jumps to the subcritical depth y_sub
    (momentum function M1 = M2)."""
    Q = _finite_positive(Q, "Discharge Q")
    y_sub = _finite_positive(y_sub, "Subcritical depth")
    yc = CriticalFlow.critical_depth(channel, Q)
    if y_sub <= yc:
        raise ValueError("The downstream depth must be subcritical (y > yc).")
    target = HydraulicJump.momentum_function(channel, y_sub, Q)
    return _bisect_root(
        lambda y: HydraulicJump.momentum_function(channel, y, Q) - target,
        1e-9, yc, label="supercritical depth",
    )


def gate_profile_with_jump(channel, Q, n, S0, y_gate, nsteps=40):
    """Sluice gate on a mild slope: an M3
    profile starts at the gate and rises until it reaches the depth y1
    conjugate to the normal depth y0, where a hydraulic jump forms."""
    info = classify_slope(channel, Q, n, S0)
    if info["class"] != "M":
        raise ValueError("This case needs a mild slope (S0 < Sc).")
    y0, yc = info["y0"], info["yc"]
    if y_gate >= yc:
        raise ValueError("The depth at the gate must be supercritical (y < yc).")
    y1 = conjugate_from_subcritical(channel, Q, y0)
    out = {**info, "y1": y1, "y2": y0, "Fr0": CriticalFlow.froude_number(channel, y0, Q)}
    if y_gate >= y1:
        out.update(jump_at_gate=True, distance=0.0, rows=[])
        return out
    rows = direct_step(channel, Q, n, S0, y_gate, y1, nsteps)
    out.update(jump_at_gate=False, distance=rows[-1]["x"], rows=rows)
    return out


# ======================================================================
# 9. DISCHARGE-DEPTH-VELOCITY TABLE
# ======================================================================

def rating_table(channel, n, S0, y_max, num_points=200):
    """Uniform-flow rating table: depth, flow area, velocity, discharge and
    Froude number at evenly spaced depths up to y_max.

    The discharge column is the same series returned by
    Manning.discharge_depth_curve, so both always agree."""
    depths, discharges = Manning.discharge_depth_curve(channel, n, S0, y_max, num_points)
    rows = []
    for y, q in zip(depths, discharges):
        if y <= 0 or q <= 0:
            rows.append({"y": y, "A": 0.0, "V": 0.0, "Q": 0.0, "Fr": 0.0})
            continue
        area = channel.area(y)
        top = channel.top_width(y)
        velocity = q / area
        fr = velocity / math.sqrt(G * area / top) if top > 0 else math.nan
        rows.append({"y": y, "A": area, "V": velocity, "Q": q, "Fr": fr})
    return rows
