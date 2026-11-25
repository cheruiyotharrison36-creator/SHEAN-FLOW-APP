"""
Benchmark verification of SHEAN FLOW APP.

Each check compares the software with a value worked out by hand from the
governing equation, or with a published benchmark case. Run with

    python test_verification.py

The script exits with status 0 only if every check passes.
"""
import math

from open_channel import (
    RectangularChannel, TrapezoidalChannel, TriangularChannel, CircularChannel,
    Manning, CriticalFlow, HydraulicJump, normal_depth_trial_table, G,
)
import hydraulic_tools as hx

results = []


def check(label, hand, software, tol):
    results.append((label, hand, software, abs(hand - software) <= tol))


def flag(label, condition):
    """Boolean check, reported as 1 = yes."""
    check(label, 1.0, 1.0 if condition else 0.0, 0)


# ======================================================================
# Section geometry (y = 1.5 m, b = 2 m, side slopes 1:1, D = 2 m)
# ======================================================================
r = RectangularChannel(b=2.0).properties(1.5)
check("Rectangle: A = b y", 3.0, r["A"], 1e-9)
check("Rectangle: P = b + 2y", 5.0, r["P"], 1e-9)
check("Rectangle: R = A/P", 0.6, r["R"], 1e-9)

z = TrapezoidalChannel(b=2.0, m=1.0, n=1.0).properties(1.5)
check("Trapezoid: A = (b + m y) y", 5.25, z["A"], 1e-9)
check("Trapezoid: P = b + 2y sqrt(1 + m^2)", 2 + 3 * math.sqrt(2), z["P"], 1e-9)
check("Trapezoid: B = b + 2 m y", 5.0, z["B"], 1e-9)

t = TriangularChannel(m=1.0, n=1.0).properties(1.5)
check("Triangle: A = m y^2", 2.25, t["A"], 1e-9)
check("Triangle: P = 2y sqrt(1 + m^2)", 3 * math.sqrt(2), t["P"], 1e-9)
check("Triangle: B = 2 m y", 3.0, t["B"], 1e-9)

c = CircularChannel(D=2.0).properties(1.0)
check("Circle, half full: A = pi D^2 / 8", math.pi / 2, c["A"], 1e-9)
check("Circle, half full: P = pi D / 2", math.pi, c["P"], 1e-9)
check("Circle, half full: B = D", 2.0, c["B"], 1e-9)
check("Circle, half full: R = D / 4", 0.5, c["R"], 1e-9)

# ======================================================================
# Uniform flow: trapezoid b = 2.4 m, side slopes 2:1, n = 0.012, S0 = 0.0001
# ======================================================================
trap = TrapezoidalChannel(b=2.4, m=2.0, n=2.0)
for y, q_ref in [(1.0, 2.724), (1.1, 3.297), (1.2, 3.933),
                 (1.25, 4.275), (1.26, 4.346), (1.27, 4.417), (1.28, 4.489)]:
    check(f"Trapezoid: Q at y = {y}", q_ref, Manning.discharge(trap, y, 0.012, 0.0001), 0.002)
y0 = Manning.normal_depth(trap, 4.5, 0.012, 0.0001)
check("Trapezoid: normal depth for Q = 4.5", 1.282, y0, 0.001)
rows, y0_trial = normal_depth_trial_table(trap, 4.5, 0.012, 0.0001, y_start=1.0)
check("Trial table: first row Q at y = 1", 2.724, rows[0]["Q computed (m³/s)"], 0.001)
check("Trial table: converged depth", 1.282, y0_trial, 0.001)

# ======================================================================
# Circular pipe D = 5 m, n = 0.013, S0 = 0.0005
# ======================================================================
D, n, S = 5.0, 0.013, 0.0005
pipe = CircularChannel(D=D)
q_full = (1 / n) * (math.pi * D ** 2 / 4) * (D / 4) ** (2 / 3) * math.sqrt(S)
check("Full pipe discharge (hand)", q_full, Manning.discharge(pipe, D, n, S), 1e-9)
ys, qs = Manning.discharge_depth_curve(pipe, n, S, D, num_points=1001)
flag("Peak discharge exceeds full-pipe discharge", max(qs) > q_full)
check("Peak discharge (m3/s)", 42.1, max(qs), 0.2)
check("Depth of peak discharge / D", 0.938, ys[qs.index(max(qs))] / D, 0.005)

# ======================================================================
# Discharge-depth-velocity table
# ======================================================================
table = hx.rating_table(pipe, n, S, D, num_points=101)
reference_q = Manning.discharge_depth_curve(pipe, n, S, D, 101)[1]
check("Rating table discharge equals Manning.discharge_depth_curve", 0.0,
      max(abs(row["Q"] - q) for row, q in zip(table, reference_q)), 1e-12)
mid = table[50]
check("Rating table: V = Q / A at y = D/2", mid["Q"] / mid["A"], mid["V"], 1e-12)
check("Rating table: half-full velocity equals full-pipe velocity", table[-1]["V"], mid["V"], 1e-9)

# ======================================================================
# Hydraulic jump
# ======================================================================
rect4 = RectangularChannel(b=4.0)
j = HydraulicJump.analyze(rect4, 7.5, 0.2)
check("Jump (b = 4, Q = 7.5, y1 = 0.2): sequent depth", 1.80, j["y2"], 0.01)
check("Jump: upstream Froude number", 6.69, j["Fr1"], 0.02)
check("Jump: downstream Froude number", 0.25, j["Fr2"], 0.01)
check("Jump: head loss (y2 - y1)^3 / (4 y1 y2)",
      (j["y2"] - 0.2) ** 3 / (4 * 0.2 * j["y2"]), j["head_loss"], 1e-6)
check("Jump: power dissipated (kW)", 208.5, j["power_kw"], 1.0)

k = HydraulicJump.rectangular_from_froude(0.4, 5.0)
check("Rectangular jump from Fr1 = 5, y1 = 0.4: y2", 2.635, k["y2"], 0.005)
lengths = list(k["lengths"].values())
check("Length, Smetana 6 (y2 - y1)", 6 * (k["y2"] - 0.4), lengths[0], 1e-9)
check("Length, Bakhmeteff-Matzke 5 (y2 - y1)", 5 * (k["y2"] - 0.4), lengths[1], 1e-9)
check("Length, Douma 5.2 y2", 5.2 * k["y2"], lengths[2], 1e-9)
check("Length, Page 5.6 y2", 5.6 * k["y2"], lengths[3], 1e-9)
check("Length, Safranez 6 y1 Fr1", 12.0, lengths[4], 1e-9)
check("Design length is the longest", max(lengths), k["design_length"], 1e-12)

check("General solver equals the rectangular formula",
      HydraulicJump.rectangular_from_froude(0.2, CriticalFlow.froude_number(rect4, 0.2, 7.5))["y2"],
      HydraulicJump.conjugate_depth(rect4, 7.5, 0.2), 1e-6)

tri = TriangularChannel(m=2.5, n=2.5)
check("Triangular jump (Q = 20, y1 = 0.75): momentum function M1", 29.35,
      HydraulicJump.momentum_function(tri, 0.75, 20.0), 0.02)
check("Triangular jump: sequent depth", 3.22, HydraulicJump.conjugate_depth(tri, 20.0, 0.75), 0.01)

m1, m2, force = HydraulicJump.force_on_obstacle(RectangularChannel(b=5.0), 14.0, 2.0, 0.5)
check("Gate force (b = 5, Q = 14, y1 = 2, y2 = 0.5): M1", 12.0, m1, 0.01)
check("Gate force: M2", 8.62, m2, 0.01)
check("Gate force: F (kN)", 33.1, force, 0.15)

drag = HydraulicJump.drag_force(0.25, 4.0 * 0.15, 7.5 / (4.0 * 0.2))
check("Baffle blocks: drag force (kN)", 6.6, drag, 0.02)
jb = HydraulicJump.analyze(rect4, 7.5, 0.2, force_kN=6.6)
check("Baffle blocks: sequent depth", 1.70, jb["y2"], 0.02)
check("Baffle blocks: energy loss (m)", 2.94, jb["head_loss"], 0.03)

w, y_surge = HydraulicJump.surge_speed(1.5, 2.5, 0.0)
check("Surge after gate closure (y1 = 1.5, V1 = 2.5): speed", 3.41, w, 0.01)
check("Surge: depth behind the surge", 2.60, y_surge, 0.01)

# ======================================================================
# Most efficient sections and partly full pipes
# ======================================================================
bs = hx.best_section(10.0, 0.015, 0.001)
check("Best trapezoid: A / y^2 = sqrt(3)", math.sqrt(3), bs["A"] / bs["y"] ** 2, 1e-9)
check("Best trapezoid: P / y = 2 sqrt(3)", 2 * math.sqrt(3), bs["P"] / bs["y"], 1e-9)
check("Best trapezoid: R / y = 1/2", 0.5, bs["R"] / bs["y"], 1e-9)
check("Best trapezoid: side angle (degrees)", 60.0, bs["side_angle_deg"], 1e-9)
check("Best rectangle: b / y = 2", 2.0, hx.best_section(10.0, 0.015, 0.001, 0.0)["b_over_y"], 1e-9)
check("Best trapezoid carries the design discharge", 10.0,
      Manning.discharge(TrapezoidalChannel(bs["b"], bs["m"], bs["m"]), bs["y"], 0.015, 0.001), 1e-6)

half = hx.circular_partial_flow(1.5, 0.75)
check("Half-full pipe: V / Vfull", 1.0, half["V/Vf"], 1e-9)
check("Half-full pipe: Q / Qfull", 0.5, half["Q/Qf"], 1e-9)

# ======================================================================
# Solve the Chezy-Manning equation for each unknown
# ======================================================================
m_side = hx.slope_from_side_angle(40.0)
check("Side slope from a 40 degree side angle", 1.191754, m_side, 1e-5)
sol = hx.solve_uniform("trapezoidal", "S0", Q=60.0, y=3.2, n=0.014, b=5.0, m1=m_side, m2=m_side)
check("Required slope (Q = 60, y = 3.2, b = 5, n = 0.014)", 0.000381, sol["S0"], 1e-6)
for unknown, true_value in (("Q", 60.0), ("y", 3.2), ("n", 0.014), ("b", 5.0)):
    kwargs = dict(Q=60.0, y=3.2, n=0.014, S0=sol["S0"], b=5.0, m1=m_side, m2=m_side)
    kwargs.pop(unknown)
    check(f"Solving for {unknown} recovers the original value", true_value,
          hx.solve_uniform("trapezoidal", unknown, **kwargs)[unknown], 1e-6)

# ======================================================================
# Flow properties
# ======================================================================
flag("Reynolds class, Re = 400 is laminar", hx.reynolds_class(400) == "Laminar")
flag("Reynolds class, Re = 1000 is transitional", hx.reynolds_class(1000) == "Transitional")
flag("Reynolds class, Re = 5000 is turbulent", hx.reynolds_class(5000) == "Turbulent")
fp = hx.flow_properties(RectangularChannel(b=0.3), 0.1, 0.08)
check("Flume (b = 0.3, y = 0.1, Q = 0.08): Froude number", 2.69, fp["Fr"], 0.01)
fp2 = hx.flow_properties(RectangularChannel(b=2.0), 1.0, 2.0, n=0.013, S0=0.001, nu=1.004e-6)
check("Wall shear stress: gamma R S0 (N/m2)", 9810 * (2.0 / 4.0) * 0.001, fp2["tau0"], 1e-9)
check("Chezy C = R^(1/6)/n", 0.5 ** (1 / 6) / 0.013, fp2["chezy_C"], 1e-9)
check("Reynolds number V R / nu", (2.0 / 2.0) * 0.5 / 1.004e-6, fp2["Re"], 1e-3)
check("Chezy C from the Fanning friction factor", math.sqrt(8 * G / 0.02), hx.chezy_from_fanning(0.02), 1e-9)

# ======================================================================
# Specific energy, alternate depth and transitions
# ======================================================================
tri1 = TriangularChannel(m=1.0, n=1.0)
fp_t = hx.flow_properties(tri1, 2.5, 3.0)
check("Triangular (m = 1, Q = 3, y = 2.5): specific energy", 2.512,
      CriticalFlow.specific_energy(tri1, 2.5, 3.0), 0.001)
check("Triangular: Froude number", 0.137, fp_t["Fr"], 0.001)
check("Triangular: hydraulic depth A/B", 1.25, fp_t["hydraulic_depth"], 1e-9)
for method in ("bisection", "newton", "trial"):
    alt = hx.alternate_depth(tri1, 3.0, 2.5, method)["alternate"]
    check(f"Alternate depth, {method}", 0.7103, alt, 0.001)

unit = RectangularChannel(b=1.0)
for q_val, y_val in [(2.0, 0.4), (2.0, 0.6), (10.0, 1.0), (10.0, 3.0), (20.0, 0.4), (20.0, 5.0)]:
    check(f"E = y + q^2 / (2 g y^2), q = {q_val:g}, y = {y_val:g}",
          y_val + q_val ** 2 / (2 * G * y_val ** 2),
          CriticalFlow.specific_energy(unit, y_val, q_val), 1e-9)

rect3 = RectangularChannel(b=3.0)
q_step = 1.55 * 1.83 * 3.0
step = hx.transition(rect3, rect3, q_step, 1.55, 0.2)
check("Bed step: upstream specific energy", 1.72, step["E1"], 0.01)
check("Bed step: critical depth", 0.94, step["yc2"], 0.01)
check("Bed step: minimum specific energy", 1.41, step["Ec2"], 0.01)
check("Bed step: critical step height", 0.31, step["critical_rise"], 0.01)
check("Bed step: upstream Froude number", 0.469, step["Fr1"], 0.001)
flag("Bed step of 0.2 m is not choked", not step["choked"])
flag("Bed step of 0.5 m is choked", hx.transition(rect3, rect3, q_step, 1.55, 0.5)["choked"])

entrance = hx.entrance_critical(TrapezoidalChannel(b=5.0, m=2.0, n=2.0), 2.3)
check("Reservoir entrance: critical depth", 1.70, entrance["yc"], 0.01)
check("Reservoir entrance: discharge", 49.3, entrance["Q"], 0.4)
check("Smallest rectangular width that passes Q at energy E", 3.0,
      hx.critical_width_rectangular(3.0 * math.sqrt(G * (2 * 1.8 / 3) ** 3), 1.8), 1e-9)

# ======================================================================
# Weirs and flumes
# ======================================================================
check("Broad-crested weir coefficient", 1.705, hx.broad_crested_weir(1.0, 1.0), 0.001)
rehbock = (2 / 3) * (0.611 + 0.075 * 0.35 / 1.47) * math.sqrt(2 * G) * 1.25 * 0.35 ** 1.5
check("Sharp-crested weir, Rehbock coefficient", rehbock,
      hx.sharp_crested_weir(1.25, 0.35, 1.47, "Rehbock"), 1e-9)
kc = (2 / 3) * (0.602 + 0.075 * 0.35 / 1.47) * math.sqrt(2 * G) * 1.25 * 0.351 ** 1.5
check("Sharp-crested weir, Kindsvater-Carter (head + 1 mm)", kc,
      hx.sharp_crested_weir(1.25, 0.35, 1.47, "Kindsvater–Carter"), 1e-9)
contracted = ((2 / 3) * (0.611 + 0.075 * 0.35 / 1.47) * math.sqrt(2 * G)
              * (1.25 - 0.2 * 0.35) * 0.35 ** 1.5)
check("Sharp-crested weir, two end contractions use b - 0.2 H", contracted,
      hx.sharp_crested_weir(1.25, 0.35, 1.47, "Rehbock", end_contractions=2), 1e-9)
check("V-notch coefficient, 60 degrees", 0.79, hx.v_notch_weir(60.0, 1.0), 0.005)
check("V-notch coefficient, 90 degrees", 1.37, hx.v_notch_weir(90.0, 1.0), 0.005)
q_francis = 1.84 * 3.0 * 0.4 ** 1.5
check("Francis, suppressed: discharge", q_francis, hx.francis_weir(3.0, 0.4, 0), 1e-9)
check("Francis, suppressed: head from discharge", 0.4,
      hx.head_for_discharge(lambda H: hx.francis_weir(3.0, H, 0), q_francis), 1e-6)
check("Francis, both ends contracted: head from discharge", 0.4,
      hx.head_for_discharge(lambda H: hx.francis_weir(3.0, H, 2),
                            hx.francis_weir(3.0, 0.4, 2), hi=3.0), 1e-6)
check("Parshall flume, 1 ft throat and 1 ft head (4 cfs, in m3/s)", 4 * 0.028316846592,
      hx.parshall_flume(0.3048, 0.3048), 1e-9)

# ======================================================================
# Gradually varied flow
# ======================================================================
rect_g = RectangularChannel(b=3.0)
g = hx.gate_profile_with_jump(rect_g, 5.0, 0.015, 0.0005, 0.15)
check("Gate on a mild slope: normal depth", 1.39, g["y0"], 0.01)
check("Gate on a mild slope: critical depth", 0.66, g["yc"], 0.01)
check("Gate on a mild slope: Froude number at y0", 0.325, g["Fr0"], 0.001)
check("Gate on a mild slope: depth before the jump", 0.25, g["y1"], 0.005)
flag("Slope is classed mild", g["class"] == "M")
flag("Profile is M3", hx.profile_name("M", 0.15, g["y0"], g["yc"]) == "M3")
pts = hx.rk4_profile(rect_g, 5.0, 0.015, 0.0005, 0.15, g["distance"], 400)
check("Direct step agrees with Runge-Kutta (M3 profile)", g["y1"], pts[-1][1], 0.002)
m1_rows = hx.direct_step(rect_g, 5.0, 0.015, 0.0005, 2.5, 1.45, 60)
pts = hx.rk4_profile(rect_g, 5.0, 0.015, 0.0005, 2.5, m1_rows[-1]["x"], 1200)
check("Direct step agrees with Runge-Kutta (M1 backwater)", 1.45, pts[-1][1], 0.005)
sc = hx.critical_slope(rect_g, 5.0, 0.015)
flag("S0 = Sc is classed critical", hx.classify_slope(rect_g, 5.0, 0.015, sc)["class"] == "C")

# ======================================================================
# Report
# ======================================================================
print(f"{'Check':<64}{'Reference':>12}{'Software':>12}  Result")
print("-" * 100)
for label, hand, soft, ok in results:
    print(f"{label:<64}{hand:>12.4f}{soft:>12.4f}  {'PASS' if ok else 'FAIL'}")
passed = sum(1 for *_, ok in results if ok)
print("-" * 100)
print(f"{passed} of {len(results)} checks passed.")
raise SystemExit(0 if passed == len(results) else 1)
