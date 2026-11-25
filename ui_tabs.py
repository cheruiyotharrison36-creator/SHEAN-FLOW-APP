"""
Tab screens for SHEAN FLOW APP.

Each render_* function draws one tab of the application. The calculations
themselves live in open_channel.py and hydraulic_tools.py.
"""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import streamlit as st

from open_channel import (
    RectangularChannel, CircularChannel, CriticalFlow, HydraulicJump, G,
)
import hydraulic_tools as hx
from ui_common import (
    CATCH, fmt, number, roughness_controls, rows_to_dict, record,
    show_error, show_table, table_payload,
)


def _energy_plot(channel, Q, marks, y_top=None):
    """E–y diagram for constant Q with labelled points [(label, y)]."""
    yc = CriticalFlow.critical_depth(channel, Q)
    top = y_top or max([y for _, y in marks] + [yc]) * 1.6
    curve = hx.specific_energy_curve(channel, Q, top, 300)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot([e for _, e in curve], [y for y, _ in curve], color="#0b6e8a", linewidth=2,
            label=f"E–y curve, Q = {Q:g} m³/s")
    ax.plot([0, curve[-1][1]], [0, curve[-1][1]], "--", color="gray", linewidth=1, label="E = y")
    ax.axhline(yc, color="#b4380c", linestyle=":", linewidth=1.2, label=f"yc = {yc:.3f} m")
    for label, y in marks:
        e = CriticalFlow.specific_energy(channel, y, Q)
        ax.plot([e], [y], "o", color="#17302b")
        ax.annotate(label, (e, y), textcoords="offset points", xytext=(6, 6), fontsize=9)
    ax.set_xlabel("Specific energy E (m)")
    ax.set_ylabel("Depth y (m)")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def _props_rows(props, channel=None, y=None):
    rows = [
        {"Quantity": "Flow area, A", "Value": fmt(props["A"], "m²")},
        {"Quantity": "Wetted perimeter, P", "Value": fmt(props["P"], "m")},
        {"Quantity": "Top width, B", "Value": fmt(props["B"], "m")},
        {"Quantity": "Hydraulic radius, R", "Value": fmt(props["R"], "m")},
        {"Quantity": "Hydraulic depth, A/B", "Value": fmt(props["hydraulic_depth"], "m")},
        {"Quantity": "Velocity, V", "Value": fmt(props["V"], "m/s")},
        {"Quantity": "Froude number, Fr", "Value": fmt(props["Fr"])},
        {"Quantity": "Flow regime", "Value": props["regime"]},
        {"Quantity": "Reynolds number, Re = VR/ν", "Value": f"{props['Re']:,.0f}"},
        {"Quantity": "Flow state (from Re)", "Value": props["flow_type"]},
        {"Quantity": "Wall shear stress, τ₀ = γRS₀", "Value": fmt(props["tau0"], "N/m²")},
        {"Quantity": "Chezy C = R^(1/6)/n", "Value": fmt(props["chezy_C"], "m^(1/2)/s")},
    ]
    if isinstance(channel, CircularChannel) and y is not None:
        theta = math.degrees(channel._theta(y))
        rows.insert(0, {"Quantity": "Central angle, θ", "Value": fmt(theta, "°", 2)})
    return rows


# ======================================================================
# TAB: UNIFORM FLOW TOOLS
# ======================================================================

def render_uniform_tools(channel):

    st.subheader("Uniform flow tools")
    st.write(
        "Solve the Chezy–Manning equation for any one unknown, check flow "
        "properties, work with partly full pipes and size the most efficient section."
    )

    modes = [
        "Solve for any unknown (Q, y₀, n, S₀ or b)",
        "Flow properties (Fr, Re, shear stress, Chezy C)",
        "Partly full circular pipe",
        "Best hydraulic (efficient) section",
    ]
    mode = st.radio("Problem", modes, key="ut_mode")
    kind, params = hx.channel_kind(channel)

    # ---------------------------------------------------------- solver
    if mode == modes[0]:

        st.caption("Uses the channel shape and dimensions chosen in the sidebar. "
                   "Choose the quantity to find and enter the others.")
        options = {"Discharge, Q": "Q", "Normal depth, y₀": "y",
                   "Roughness, n": "n", "Bed slope, S₀": "S0"}
        if kind in ("rectangular", "trapezoidal"):
            options["Bottom width, b"] = "b"
        label = st.selectbox("Find", list(options.keys()), key="ut_unknown")
        unknown = options[label]

        c1, c2 = st.columns(2)
        with c1:
            q_in = number("Discharge, Q (m³/s)", "ut_q", 4.5, step=0.5) if unknown != "Q" else None
            n_in = number("Manning’s n", "ut_n", 0.012, step=0.001) if unknown != "n" else None
        with c2:
            y_in = number("Depth, y (m)", "ut_y", 1.0, step=0.1) if unknown != "y" else None
            s_in = number("Bed slope, S₀ (m/m)", "ut_s", 0.0001, step=0.0001,
                        fmt_str="%.6f", minimum=0.000001) if unknown != "S0" else None

        if st.button("Solve", type="primary", width="stretch", key="ut_go"):
            try:
                res = hx.solve_uniform(
                    kind, unknown, Q=q_in, y=y_in, n=n_in, S0=s_in,
                    b=params.get("b"), m1=params.get("m1"),
                    m2=params.get("m2"), D=params.get("D"),
                )
                solved = res[unknown]
                digits = 6 if unknown in ("n", "S0") else 4
                unit = {"Q": "m³/s", "y": "m", "b": "m", "n": "", "S0": ""}[unknown]
                st.metric(label, fmt(solved, unit, digits))
                show_table(_props_rows(res["props"], res["channel"], res["y"]))
                st.latex(r"Q = \frac{1}{n} A R^{2/3} S_0^{1/2}")
                known = {}
                if q_in is not None:
                    known["Discharge, Q"] = fmt(q_in, "m³/s")
                if y_in is not None:
                    known["Depth, y"] = fmt(y_in, "m")
                if n_in is not None:
                    known["Manning's n"] = fmt(n_in, "", 4)
                if s_in is not None:
                    known["Bed slope, S0"] = fmt(s_in, "", 6)
                record("ut_solve", f"Uniform flow: solve for {label[0].lower() + label[1:]}",
                       "Chezy-Manning equation Q = (1/n) A R^(2/3) S0^(1/2)",
                       known,
                       {label: fmt(solved, unit, digits),
                        **rows_to_dict(_props_rows(res["props"], res["channel"], res["y"]))},
                       channel=res["channel"])
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- properties
    elif mode == modes[1]:

        c1, c2 = st.columns(2)
        with c1:
            y = number("Depth, y (m)", "fp_y", 1.0)
            n = number("Manning’s n", "fp_n", 0.013, step=0.001)
        with c2:
            q = number("Discharge, Q (m³/s)", "fp_q", 2.0, step=0.5)
            s = number("Bed slope, S₀ (m/m)", "fp_s", 0.001, step=0.0001,
                     fmt_str="%.6f", minimum=0.000001)
        nu = st.number_input("Kinematic viscosity, ν (m²/s)", value=1.004e-6,
                             format="%.3e", key="fp_nu")
        if st.button("Calculate properties", type="primary", width="stretch", key="fp_go"):
            try:
                props = hx.flow_properties(channel, y, q, n=n, S0=s, nu=nu)
                show_table(_props_rows(props, channel, y))
                record("ut_props", "Flow properties at a given depth",
                       "Fr = V / sqrt(g A/B), Re = V R / nu, tau0 = gamma R S0, C = R^(1/6) / n",
                       {"Depth, y": fmt(y, "m"), "Discharge, Q": fmt(q, "m³/s"),
                        "Manning's n": fmt(n, "", 4), "Bed slope, S0": fmt(s, "", 6),
                        "Kinematic viscosity": f"{nu:.3e} m²/s"},
                       rows_to_dict(_props_rows(props, channel, y)), channel=channel)
                st.caption("Re = VR/ν uses the hydraulic radius: laminar below 500, "
                           "transitional up to 2000, turbulent above.")
            except CATCH as exc:
                st.error(str(exc))

        with st.expander("Chezy C from the Fanning friction factor"):
            f_val = number("Fanning friction factor, f", "fp_f", 0.02, step=0.005, fmt_str="%.4f")
            st.write(f"C = √(8g / f) = **{fmt(hx.chezy_from_fanning(f_val), 'm^(1/2)/s')}**")

    # ---------------------------------------------------------- partly full pipe
    elif mode == modes[2]:

        st.caption("With n and S₀ constant, the velocity and discharge of a partly full "
                   "pipe follow from ratios to the full-pipe values.")
        c1, c2, c3 = st.columns(3)
        with c1:
            d = number("Pipe diameter, D (m)", "pp_d", 1.5)
        with c2:
            ratio = st.number_input("Depth ratio, y/D", min_value=0.01, max_value=1.0,
                                    value=0.5, step=0.05, format="%.3f", key="pp_ratio")
        with c3:
            v_full = number("Full-pipe velocity, Vf (m/s)", "pp_vf", 0.6, step=0.1)
        try:
            r = hx.circular_partial_flow(d, ratio * d)
            q_full = v_full * math.pi * d ** 2 / 4.0
            a, b, c = st.columns(3)
            a.metric("Velocity, V", fmt(v_full * r["V/Vf"], "m/s"))
            b.metric("Discharge, Q", fmt(q_full * r["Q/Qf"], "m³/s"))
            c.metric("Central angle, θ", fmt(r["theta_deg"], "°", 2))
            ratios = [i / 20.0 for i in range(1, 21)]
            table = []
            for z in ratios:
                rr = hx.circular_partial_flow(d, z * d)
                table.append({"y/D": z, "A/Af": rr["A/Af"], "R/Rf": rr["R/Rf"],
                              "V/Vf": rr["V/Vf"], "Q/Qf": rr["Q/Qf"]})
            fig, ax = plt.subplots(figsize=(6.5, 3.6))
            ax.plot([t["Q/Qf"] for t in table], ratios, label="Q/Qf", color="#0b6e8a", linewidth=2)
            ax.plot([t["V/Vf"] for t in table], ratios, label="V/Vf", color="#b4380c", linewidth=2)
            ax.plot([t["A/Af"] for t in table], ratios, label="A/Af", color="gray", linestyle="--")
            ax.set_xlabel("Ratio to full-pipe value")
            ax.set_ylabel("y / D")
            ax.grid(True, alpha=0.25)
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig, width="stretch")
            record("ut_pipe", "Partly full circular pipe",
                   "Velocity and discharge ratios to the full pipe at constant n and S0",
                   {"Pipe diameter, D": fmt(d, "m"), "Depth ratio, y/D": fmt(ratio, "", 3),
                    "Full-pipe velocity, Vf": fmt(v_full, "m/s")},
                   {"Velocity, V": fmt(v_full * r["V/Vf"], "m/s"),
                    "Discharge, Q": fmt(q_full * r["Q/Qf"], "m³/s"),
                    "Central angle, theta": fmt(r["theta_deg"], "°", 2),
                    "A / Af": fmt(r["A/Af"]), "V / Vf": fmt(r["V/Vf"]), "Q / Qf": fmt(r["Q/Qf"])},
                   table=table_payload(table, "Ratios to the full-pipe values"), figure=fig)
            plt.close(fig)
            with st.expander("Table of ratios"):
                show_table(table)
        except CATCH as exc:
            st.error(str(exc))

    # ---------------------------------------------------------- best section
    else:

        st.caption("The most efficient trapezoid has R = y/2. For a rectangle b = 2y; "
                   "for 60° sides A = √3 y² and P = 2√3 y.")
        c1, c2 = st.columns(2)
        with c1:
            q = number("Discharge, Q (m³/s)", "bs_q", 10.0, step=0.5)
        with c2:
            shape = st.selectbox(
                "Section",
                ["Trapezoid, 60° sides (m = 1/√3)", "Rectangle (m = 0)", "Trapezoid, chosen side slope"],
                key="bs_shape",
            )
        n, s = roughness_controls("bs")
        m = None
        if shape.startswith("Rectangle"):
            m = 0.0
        elif shape.startswith("Trapezoid, chosen"):
            m = number("Side slope, m (horizontal per 1 vertical)", "bs_m", 1.0, step=0.1)
        if st.button("Size the section", type="primary", width="stretch", key="bs_go"):
            try:
                res = hx.best_section(q, n, s, m)
                a, b, c = st.columns(3)
                a.metric("Depth, y", fmt(res["y"], "m"))
                b.metric("Bottom width, b", fmt(res["b"], "m"))
                c.metric("b / y", fmt(res["b_over_y"]))
                show_table([
                    {"Quantity": "Side slope, m", "Value": fmt(res["m"])},
                    {"Quantity": "Side angle from horizontal", "Value": fmt(res["side_angle_deg"], "°", 2)},
                    {"Quantity": "Top width, B", "Value": fmt(res["B"], "m")},
                    {"Quantity": "Area, A", "Value": fmt(res["A"], "m²")},
                    {"Quantity": "Wetted perimeter, P", "Value": fmt(res["P"], "m")},
                    {"Quantity": "Hydraulic radius, R = y/2", "Value": fmt(res["R"], "m")},
                    {"Quantity": "Velocity, V", "Value": fmt(res["V"], "m/s")},
                ])
                record("bs_best", "Best hydraulic (efficient) section",
                       "Most efficient section: R = y/2, b = 2y(sqrt(1+m^2) - m)",
                       {"Discharge, Q": fmt(q, "m³/s"), "Manning's n": fmt(n, "", 4),
                        "Bed slope, S0": fmt(s, "", 6), "Side slope, m": fmt(res["m"])},
                       {"Depth, y": fmt(res["y"], "m"), "Bottom width, b": fmt(res["b"], "m"),
                        "b / y": fmt(res["b_over_y"]), "Top width, B": fmt(res["B"], "m"),
                        "Area, A": fmt(res["A"], "m²"), "Wetted perimeter, P": fmt(res["P"], "m"),
                        "Hydraulic radius, R": fmt(res["R"], "m"), "Velocity, V": fmt(res["V"], "m/s")})
            except CATCH as exc:
                st.error(str(exc))


# ======================================================================
# TAB: SPECIFIC ENERGY AND TRANSITIONS
# ======================================================================

def render_energy(channel):

    st.subheader("Specific energy and transitions")
    st.write("Specific energy, alternate depth and flow through transitions. "
             "Uses the channel chosen in the sidebar unless stated.")

    modes = [
        "Specific energy and alternate depth",
        "Hump or step in the bed",
        "Width change (rectangular)",
        "Free entrance from a reservoir",
        "Energy loss in a transition",
    ]
    mode = st.radio("Problem", modes, key="en_mode")

    # ---------------------------------------------------------- alternate depth
    if mode == modes[0]:

        c1, c2, c3 = st.columns(3)
        with c1:
            q = number("Discharge, Q (m³/s)", "en_q", 3.0, step=0.5)
        with c2:
            y1 = number("Depth, y (m)", "en_y", 2.5)
        with c3:
            method = st.selectbox("Method", ["Bisection", "Newton–Raphson", "Trial and error"],
                                  key="en_method")
        keys = {"Bisection": "bisection", "Newton–Raphson": "newton",
                "Trial and error": "trial"}
        if st.button("Calculate", type="primary", width="stretch", key="en_go"):
            try:
                res = hx.alternate_depth(channel, q, y1, keys[method])
                v = q / channel.area(y1)
                a, b, c = st.columns(3)
                a.metric("Specific energy, E", fmt(res["E1"], "m"))
                b.metric("Froude number, Fr", fmt(res["Fr1"]))
                c.metric(f"Alternate depth ({res['branch']})", fmt(res["alternate"], "m"))
                d, e, f = st.columns(3)
                d.metric("Critical depth, yc", fmt(res["yc"], "m"))
                e.metric("Minimum energy, Ec", fmt(res["Ec"], "m"))
                f.metric("Velocity, V", fmt(v, "m/s"))
                top = channel.top_width(y1)
                if top > 0:
                    st.write(f"Hydraulic depth A/B = {channel.area(y1) / top:.4f} m.")
                fig = _energy_plot(channel, q, [("y", y1), ("alternate", res["alternate"])],
                                   y_top=max(y1, res["alternate"]) * 1.4)
                st.pyplot(fig, width="stretch")
                record("en_alt", "Specific energy and alternate depth",
                       f"Specific energy E = y + Q^2/(2 g A^2); alternate depth by the {method.lower()} method",
                       {"Discharge, Q": fmt(q, "m³/s"), "Depth, y": fmt(y1, "m"), "Method": method},
                       {"Specific energy, E": fmt(res["E1"], "m"), "Froude number": fmt(res["Fr1"]),
                        "Velocity, V": fmt(v, "m/s"), "Critical depth, yc": fmt(res["yc"], "m"),
                        "Minimum energy, Ec": fmt(res["Ec"], "m"),
                        f"Alternate depth ({res['branch']})": fmt(res["alternate"], "m")},
                       table=table_payload(res["rows"], f"Iteration table ({method.lower()})", 5),
                       figure=fig, channel=channel)
                plt.close(fig)
                if res["rows"]:
                    with st.expander(f"Iteration table ({method.lower()})", expanded=True):
                        show_table(res["rows"], 5)
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- hump
    elif mode == modes[1]:

        st.caption("The bed is raised by Δz, so E₁ = E₂ + Δz. If E₂ would fall below the "
                   "minimum specific energy Ec, the flow is choked.")
        c1, c2, c3 = st.columns(3)
        with c1:
            q = number("Discharge, Q (m³/s)", "hu_q", 8.5095, step=0.5)
        with c2:
            y1 = number("Upstream depth, y₁ (m)", "hu_y", 1.55)
        with c3:
            dz = st.number_input("Bed rise, Δz (m)", value=0.2, step=0.05,
                                 format="%.4f", key="hu_dz")
        with st.expander("Energy losses (optional)"):
            ke = number("Expansion coefficient, Ke", "hu_ke", 0.0, minimum=0.0, step=0.1)
            kc = number("Contraction coefficient, Kc", "hu_kc", 0.0, minimum=0.0, step=0.1)
            st.caption("Typical values: Ke = 1.0 sudden, 0.2 rounded; Kc = 0.5 sudden, 0.1 well designed.")
        if st.button("Calculate", type="primary", width="stretch", key="hu_go"):
            try:
                r = hx.transition(channel, channel, q, y1, dz, ke, kc)
                a, b, c = st.columns(3)
                a.metric("Upstream energy, E₁", fmt(r["E1"], "m"))
                b.metric("Upstream Froude number", fmt(r["Fr1"]))
                c.metric("Critical depth, yc", fmt(r["yc2"], "m"))
                d, e, f = st.columns(3)
                d.metric("Critical energy, Ec", fmt(r["Ec2"], "m"))
                e.metric("Critical hump height", fmt(r["critical_rise"], "m"))
                f.metric("Energy loss, hL", fmt(r["h_loss"], "m"))
                if r["choked"]:
                    st.warning(
                        f"Choked flow: critical depth {r['y2']:.4f} m occurs on the hump and "
                        f"the upstream depth rises to {r['y1_new']:.4f} m (damming)."
                    )
                else:
                    g1, g2, g3 = st.columns(3)
                    g1.metric("Depth on the hump, y₂", fmt(r["y2"], "m"))
                    g2.metric("Velocity, V₂", fmt(r["V2"], "m/s"))
                    g3.metric("Froude number, Fr₂", fmt(r["Fr2"]))
                    surface = (r["y2"] + dz) - y1
                    st.write(f"Change in water surface level = {surface:+.4f} m "
                             f"({'drop' if surface < 0 else 'rise'}).")
                marks = [("y₁", y1)] if r["choked"] else [("y₁", y1), ("y₂", r["y2"])]
                fig = _energy_plot(channel, q, marks)
                st.pyplot(fig, width="stretch")
                hump = {"Upstream energy, E1": fmt(r["E1"], "m"),
                        "Upstream Froude number": fmt(r["Fr1"]),
                        "Critical depth, yc": fmt(r["yc2"], "m"),
                        "Critical energy, Ec": fmt(r["Ec2"], "m"),
                        "Critical hump height": fmt(r["critical_rise"], "m"),
                        "Energy loss, hL": fmt(r["h_loss"], "m")}
                if r["choked"]:
                    hump["Result"] = "Choked flow"
                    hump["Depth on the hump (critical)"] = fmt(r["y2"], "m")
                    hump["Raised upstream depth"] = fmt(r["y1_new"], "m")
                else:
                    hump["Depth on the hump, y2"] = fmt(r["y2"], "m")
                    hump["Velocity, V2"] = fmt(r["V2"], "m/s")
                    hump["Froude number, Fr2"] = fmt(r["Fr2"])
                record("en_hump", "Hump or step in the bed",
                       "Energy equation E1 = E2 + dz (plus losses)",
                       {"Discharge, Q": fmt(q, "m³/s"), "Upstream depth, y1": fmt(y1, "m"),
                        "Bed rise, dz": fmt(dz, "m"), "Ke": fmt(ke, "", 2), "Kc": fmt(kc, "", 2)},
                       hump, figure=fig, channel=channel)
                plt.close(fig)
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- width change
    elif mode == modes[2]:

        st.caption("A rectangular channel narrows or widens from b₁ to b₂ (bed rise Δz optional). "
                   "Independent of the sidebar channel.")
        c1, c2, c3 = st.columns(3)
        with c1:
            q = number("Discharge, Q (m³/s)", "wc_q", 8.5095, step=0.5)
            b1 = number("Width before, b₁ (m)", "wc_b1", 3.0)
        with c2:
            y1 = number("Depth before, y₁ (m)", "wc_y", 1.55)
            b2 = number("Width after, b₂ (m)", "wc_b2", 2.5)
        with c3:
            dz = st.number_input("Bed rise, Δz (m)", value=0.0, step=0.05,
                                 format="%.4f", key="wc_dz")
        if st.button("Calculate", type="primary", width="stretch", key="wc_go"):
            try:
                ch1, ch2 = RectangularChannel(b1), RectangularChannel(b2)
                r = hx.transition(ch1, ch2, q, y1, dz)
                b_min = hx.critical_width_rectangular(q, r["E1"] - dz)
                a, b, c = st.columns(3)
                a.metric("Upstream energy, E₁", fmt(r["E1"], "m"))
                b.metric("Critical depth after, yc", fmt(r["yc2"], "m"))
                c.metric("Smallest width that does not choke", fmt(b_min, "m"))
                if r["choked"]:
                    st.warning(
                        f"Choked flow: critical depth {r['y2']:.4f} m occurs in the narrow "
                        f"section and the upstream depth rises to {r['y1_new']:.4f} m."
                    )
                else:
                    d, e, f = st.columns(3)
                    d.metric("Depth after, y₂", fmt(r["y2"], "m"))
                    e.metric("Velocity after, V₂", fmt(r["V2"], "m/s"))
                    f.metric("Froude number after", fmt(r["Fr2"]))
                width = {"Upstream energy, E1": fmt(r["E1"], "m"),
                         "Critical depth after, yc": fmt(r["yc2"], "m"),
                         "Smallest width that does not choke": fmt(b_min, "m")}
                if r["choked"]:
                    width["Result"] = "Choked flow"
                    width["Raised upstream depth"] = fmt(r["y1_new"], "m")
                else:
                    width["Depth after, y2"] = fmt(r["y2"], "m")
                    width["Velocity after, V2"] = fmt(r["V2"], "m/s")
                    width["Froude number after"] = fmt(r["Fr2"])
                record("en_width", "Width change in a rectangular channel",
                       "Energy equation E1 = E2 + dz with q = Q/b",
                       {"Discharge, Q": fmt(q, "m³/s"), "Width before, b1": fmt(b1, "m"),
                        "Width after, b2": fmt(b2, "m"), "Depth before, y1": fmt(y1, "m"),
                        "Bed rise, dz": fmt(dz, "m")}, width)
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- reservoir entrance
    elif mode == modes[3]:

        st.caption("Free entrance from a reservoir (V₁ ≈ 0) with critical flow at the "
                   "crest: H = yc + A/(2B) and Q = √(gA³/B).")
        h = number("Reservoir level above the crest, H (m)", "re_h", 2.3, step=0.1)
        if st.button("Calculate", type="primary", width="stretch", key="re_go"):
            try:
                r = hx.entrance_critical(channel, h)
                a, b, c, d = st.columns(4)
                a.metric("Critical depth, yc", fmt(r["yc"], "m"))
                b.metric("Area, A", fmt(r["A"], "m²"))
                c.metric("Top width, B", fmt(r["B"], "m"))
                d.metric("Discharge, Q", fmt(r["Q"], "m³/s"))
                record("en_entrance", "Free entrance from a reservoir",
                       "Critical flow at the entrance: H = yc + A/(2B), Q = sqrt(g A^3 / B)",
                       {"Reservoir level above the crest, H": fmt(h, "m")},
                       {"Critical depth, yc": fmt(r["yc"], "m"), "Area, A": fmt(r["A"], "m²"),
                        "Top width, B": fmt(r["B"], "m"), "Discharge, Q": fmt(r["Q"], "m³/s")},
                       channel=channel)
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- losses
    else:

        st.caption("Head loss h_L = Ke (V₁² − V₂²)/2g for an expansion and "
                   "h_L = Kc (V₂² − V₁²)/2g for a contraction.")
        c1, c2 = st.columns(2)
        with c1:
            v1 = number("Velocity before, V₁ (m/s)", "lo_v1", 2.0)
        with c2:
            v2 = number("Velocity after, V₂ (m/s)", "lo_v2", 3.0)
        options = {
            "Contraction, sudden (Kc = 0.5)": ("c", 0.5),
            "Contraction, well designed (Kc = 0.10)": ("c", 0.10),
            "Expansion, sudden (Ke = 1.0)": ("e", 1.0),
            "Expansion, rounded (Ke = 0.2)": ("e", 0.2),
        }
        choice = st.selectbox("Transition type", list(options.keys()), key="lo_type")
        kind, k = options[choice]
        if st.button("Calculate", type="primary", width="stretch", key="lo_go"):
            loss = k * abs(v1 ** 2 - v2 ** 2) / (2.0 * G)
            st.metric("Head loss, hL", fmt(loss, "m"))
            if (kind == "c" and v2 < v1) or (kind == "e" and v2 > v1):
                st.caption("The chosen type does not match the change in velocity "
                           "(a contraction speeds the flow up, an expansion slows it down).")
            record("en_loss", "Energy loss in a transition",
                   "h_L = Ke |V1^2 - V2^2| / 2g (expansion), Kc |V2^2 - V1^2| / 2g (contraction)",
                   {"Velocity before, V1": fmt(v1, "m/s"), "Velocity after, V2": fmt(v2, "m/s"),
                    "Transition type": choice},
                   {"Head loss, hL": fmt(loss, "m")})


# ======================================================================
# TAB: GRADUALLY VARIED FLOW
# ======================================================================

def _default_end_depth(name, y_start, y0, yc):
    if name in ("M1", "S2"):
        return y0 + 0.05 * (y_start - y0)
    if name in ("M2", "S3"):
        return y0 - 0.05 * (y0 - y_start)
    if name in ("S1", "C1"):
        return yc + 0.3 * (y_start - yc)
    if name in ("M3", "C3", "H3", "A3"):
        return y_start + 0.7 * (yc - y_start)
    return 1.3 * y_start            # H2, A2


def _profile_plot(channel, rows_x, rows_y, y0, yc, title):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(rows_x, rows_y, color="#0b6e8a", linewidth=2.2, label="Water surface (depth y)")
    if y0 is not None:
        ax.axhline(y0, color="#17302b", linestyle="--", linewidth=1, label=f"y₀ = {y0:.3f} m")
    ax.axhline(yc, color="#b4380c", linestyle=":", linewidth=1.3, label=f"yc = {yc:.3f} m")
    ax.set_xlabel("Distance x in the flow direction from the control (m)")
    ax.set_ylabel("Depth y (m)")
    ax.set_title(title, fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def render_gvf(channel):

    st.subheader("Gradually varied flow")
    st.write("Slope classification, water surface profiles and the direct step method.")

    modes = [
        "Classify slope and compute a profile",
        "Sluice gate, M3 profile and hydraulic jump",
    ]
    mode = st.radio("Problem", modes, key="gv_mode")

    c1, c2 = st.columns(2)
    with c1:
        q = number("Discharge, Q (m³/s)", "gv_q", 5.0, step=0.5)

    # ---------------------------------------------------------- profile
    if mode == modes[0]:

        n, s0 = roughness_controls("gv", default_slope=0.0005, allow_flat=True)
        with c2:
            y_start = number("Depth at the control, y (m)", "gv_y", 2.5)
        try:
            info = hx.classify_slope(channel, q, n, s0)
            name = hx.profile_name(info["class"], y_start, info["y0"], info["yc"])
            kind, rng = hx.PROFILE_INFO[name]
            a, b, c, d = st.columns(4)
            a.metric("Slope class", f"{info['name']} ({info['class']})")
            b.metric("Normal depth, y₀", fmt(info["y0"], "m") if info["y0"] else "none")
            c.metric("Critical depth, yc", fmt(info["yc"], "m"))
            d.metric("Critical slope, Sc", fmt(info["Sc"], "", 6))
            fr = CriticalFlow.froude_number(channel, y_start, q)
            direction = "upstream" if fr < 1 else "downstream"
            st.info(f"Profile **{name}** ({kind.lower()} curve, {rng}). The flow is "
                    f"{'subcritical' if fr < 1 else 'supercritical'}, so compute {direction} "
                    "from the control.")
        except CATCH as exc:
            st.error(str(exc))
            return

        default_end = _default_end_depth(name, y_start, info["y0"] or y_start, info["yc"])
        e1, e2, e3 = st.columns(3)
        with e1:
            y_end = number("Final depth, y (m)", f"gv_end_{name}_{y_start:.4f}_{q:g}",
                         float(max(default_end, 0.001)))
        with e2:
            nsteps = st.number_input("Number of steps", min_value=2, max_value=400,
                                     value=30, step=5, key="gv_steps")
        with e3:
            method = st.selectbox("Method", ["Direct step", "Numerical integration (RK4)"],
                                  key="gv_method")
        if st.button("Compute profile", type="primary", width="stretch", key="gv_go"):
            try:
                rows = hx.direct_step(channel, q, n, s0, y_start, y_end, int(nsteps))
                length = rows[-1]["x"]
                if method.startswith("Numerical"):
                    pts = hx.rk4_profile(channel, q, n, s0, y_start, length, 200)
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    st.write(f"Reach length from the direct step method: {abs(length):,.2f} m; "
                             f"RK4 depth at that distance: {ys[-1]:.4f} m.")
                else:
                    xs, ys = [r["x"] for r in rows], [r["y"] for r in rows]
                    st.write(f"Distance from y = {y_start:.3f} m to y = {y_end:.3f} m: "
                             f"**{abs(length):,.2f} m** "
                             f"({'upstream' if length < 0 else 'downstream'} of the control).")
                fig = _profile_plot(channel, xs, ys, info["y0"], info["yc"], f"{name} profile")
                st.pyplot(fig, width="stretch")
                step_rows = [
                    {"y (m)": r["y"], "V (m/s)": r["V"], "E (m)": r["E"], "Fr": r["Fr"],
                     "Sf": r["Sf"], "dx (m)": r["dx"], "x (m)": r["x"]}
                    for r in rows
                ]
                record("gv_profile", f"Water surface profile {name}",
                       "Direct step method: dx = (E2 - E1) / (S0 - Sf mean)",
                       {"Discharge, Q": fmt(q, "m³/s"), "Manning's n": fmt(n, "", 4),
                        "Bed slope, S0": fmt(s0, "", 6), "Depth at the control": fmt(y_start, "m"),
                        "Final depth": fmt(y_end, "m"), "Number of steps": str(int(nsteps))},
                       {"Slope class": f"{info['name']} ({info['class']})",
                        "Normal depth, y0": fmt(info["y0"], "m") if info["y0"] else "none",
                        "Critical depth, yc": fmt(info["yc"], "m"),
                        "Critical slope, Sc": fmt(info["Sc"], "", 6),
                        "Profile": f"{name} ({kind.lower()})",
                        "Reach length": fmt(abs(length), "m", 2)
                        + (" upstream" if length < 0 else " downstream")},
                       table=table_payload(step_rows, "Direct step table", 4),
                       figure=fig, channel=channel)
                plt.close(fig)
                with st.expander("Direct step table", expanded=True):
                    show_table([
                        {"y (m)": r["y"], "A (m²)": r["A"], "V (m/s)": r["V"], "E (m)": r["E"],
                         "Fr": r["Fr"], "Sf": r["Sf"], "Δx (m)": r["dx"], "x (m)": r["x"]}
                        for r in rows
                    ], 5)
                st.latex(r"\Delta x = \frac{E_2 - E_1}{S_0 - \bar S_f}, \qquad "
                         r"\frac{dy}{dx} = \frac{S_0 - S_f}{1 - Fr^2}")
            except CATCH as exc:
                st.error(str(exc))

    # ---------------------------------------------------------- gate and jump
    else:

        n, s0 = roughness_controls("gj", default_slope=0.0005)
        with c2:
            y_gate = number("Depth at the gate, y (m)", "gj_y", 0.15, step=0.05)
        if st.button("Analyse", type="primary", width="stretch", key="gj_go"):
            try:
                r = hx.gate_profile_with_jump(channel, q, n, s0, y_gate)
                a, b, c, d = st.columns(4)
                a.metric("Normal depth, y₀", fmt(r["y0"], "m"))
                b.metric("Critical depth, yc", fmt(r["yc"], "m"))
                c.metric("Froude number at y₀", fmt(r["Fr0"]))
                d.metric("Depth before the jump, y₁", fmt(r["y1"], "m"))
                gate_fig = None
                if r["jump_at_gate"]:
                    st.warning("The jump forms right at the gate.")
                else:
                    st.success(f"M3 profile from the gate, then a hydraulic jump "
                               f"{r['distance']:,.2f} m downstream of the gate, from "
                               f"{r['y1']:.3f} m to {r['y2']:.3f} m.")
                    rows = r["rows"]
                    fig = _profile_plot(channel, [p["x"] for p in rows], [p["y"] for p in rows],
                                        r["y0"], r["yc"], "M3 profile up to the jump")
                    st.pyplot(fig, width="stretch")
                    gate_fig = fig
                    with st.expander("Direct step table"):
                        show_table([
                            {"y (m)": p["y"], "V (m/s)": p["V"], "E (m)": p["E"],
                             "Fr": p["Fr"], "Sf": p["Sf"], "Δx (m)": p["dx"], "x (m)": p["x"]}
                            for p in rows
                        ], 5)
                gate_rows = [
                    {"y (m)": p["y"], "V (m/s)": p["V"], "E (m)": p["E"], "Fr": p["Fr"],
                     "Sf": p["Sf"], "dx (m)": p["dx"], "x (m)": p["x"]}
                    for p in r["rows"]
                ]
                record("gj_gate", "Sluice gate, M3 profile and hydraulic jump",
                       "M3 profile from the gate up to the depth conjugate to y0, then a hydraulic jump",
                       {"Discharge, Q": fmt(q, "m³/s"), "Manning's n": fmt(n, "", 4),
                        "Bed slope, S0": fmt(s0, "", 6), "Depth at the gate": fmt(y_gate, "m")},
                       {"Normal depth, y0": fmt(r["y0"], "m"), "Critical depth, yc": fmt(r["yc"], "m"),
                        "Froude number at y0": fmt(r["Fr0"]),
                        "Depth before the jump, y1": fmt(r["y1"], "m"),
                        "Depth after the jump, y2": fmt(r["y2"], "m"),
                        "Distance from the gate to the jump": fmt(r["distance"], "m", 2)},
                       table=table_payload(gate_rows, "Direct step table (M3 profile)", 4),
                       figure=gate_fig, channel=channel)
                if gate_fig is not None:
                    plt.close(gate_fig)
            except CATCH as exc:
                st.error(str(exc))


# ======================================================================
# TAB: WEIRS AND FLUMES
# ======================================================================


# ======================================================================
# TAB: HYDRAULIC JUMP AND MOMENTUM
# ======================================================================

def _jump_results(res):
    """Display the results of a hydraulic jump calculation."""
    a, b, c = st.columns(3)
    a.metric("Sequent depth, y₂", fmt(res["y2"], "m"))
    b.metric("Upstream Froude number, Fr₁", fmt(res["Fr1"]))
    c.metric("Downstream Froude number, Fr₂", fmt(res["Fr2"]))

    d, e, f = st.columns(3)
    d.metric("Head loss, hⱼ", fmt(res["head_loss"], "m"))
    e.metric("Power dissipated", fmt(res["power_kw"], "kW"))
    f.metric("Jump type", res["type"])

    st.write(
        f"Velocity before the jump V₁ = {res['V1']:.3f} m/s, "
        f"after the jump V₂ = {res['V2']:.3f} m/s."
    )

    with st.expander("Jump length"):
        show_table(
            [{"Method": name, "Length (m)": round(value, 2)}
             for name, value in res["lengths"].items()],
        )
        st.write(f"Design length (longest value): **{res['design_length']:.2f} m**")
        st.caption(
            "Empirical formulas for a jump in a rectangular channel. The longest "
            "value is a conservative estimate; stilling-basin design charts give "
            "a more reliable basin length."
        )


def _jump_record(key, title, basis, inputs, res, channel=None):
    results = {
        "Sequent depth, y2": fmt(res["y2"], "m"),
        "Upstream Froude number, Fr1": fmt(res["Fr1"]),
        "Downstream Froude number, Fr2": fmt(res["Fr2"]),
        "Velocity before the jump, V1": fmt(res["V1"], "m/s"),
        "Velocity after the jump, V2": fmt(res["V2"], "m/s"),
        "Head loss": fmt(res["head_loss"], "m"),
        "Power dissipated": fmt(res["power_kw"], "kW"),
        "Jump type": res["type"],
        "Design length (longest empirical value)": fmt(res["design_length"], "m", 2),
    }
    record(
        key, title, basis, inputs, results,
        table=table_payload(
            [{"Method": k, "Length (m)": round(v, 2)} for k, v in res["lengths"].items()],
            "Empirical jump lengths",
        ),
        channel=channel,
    )


def render_jump(channel):

    st.subheader("Hydraulic jump and momentum")
    st.write(
        "Hydraulic jump, moving surge and force calculations from the momentum "
        "equation. A hydraulic jump forms when supercritical flow changes to "
        "subcritical flow."
    )

    modes = [
        "Jump in the selected channel (Q and y₁)",
        "Rectangular channel (Fr₁ and y₁)",
        "Moving surge or bore",
        "Force on a gate or obstacle",
    ]
    mode = st.radio("Problem", modes, key="jump_mode")

    # ---------------------------------------------------------- selected channel
    if mode == modes[0]:

        st.caption(
            "Uses the channel chosen in the sidebar and the momentum equation "
            "M₁ = M₂. Upstream flow must be supercritical."
        )
        c1, c2 = st.columns(2)
        with c1:
            q = number("Discharge, Q (m³/s)", "j1_q", 7.5, step=0.5)
        with c2:
            y1 = number("Upstream depth, y₁ (m)", "j1_y1", 0.2, step=0.05)

        with st.expander("Baffle blocks or other obstacles in the jump"):
            cd = number("Drag coefficient, CD (0 = no obstacles)", "j1_cd", 0.0,
                        minimum=0.0, step=0.05, fmt_str="%.3f")
            area = number("Frontal area of the blocks, A (m²)", "j1_area", 0.0,
                          minimum=0.0, step=0.05)
            st.caption("Drag force F = CD A ρ V₁² / 2, used in the momentum "
                       "equation M₂ = M₁ − F/γ.")

        if st.button("Analyse hydraulic jump", type="primary", width="stretch", key="j1_go"):
            try:
                force = 0.0
                if cd > 0 and area > 0:
                    force = HydraulicJump.drag_force(cd, area, q / channel.area(y1))
                    st.write(f"Drag force on the blocks: **{force * 1000:,.0f} N**")
                res = HydraulicJump.analyze(channel, q, y1, force_kN=force)
                _jump_results(res)
                inputs = {"Discharge, Q": fmt(q, "m³/s"), "Upstream depth, y1": fmt(y1, "m")}
                if force:
                    inputs["Force of the blocks"] = fmt(force * 1000, "N", 0)
                _jump_record("jp_channel", "Hydraulic jump in the selected channel",
                             "Momentum equation M1 = M2 + F/gamma", inputs, res, channel)
            except CATCH as exc:
                show_error(exc)

    # ---------------------------------------------------------- rectangular
    elif mode == modes[1]:

        st.caption(
            "Uses y₂/y₁ = ½(√(1 + 8Fr₁²) − 1) and hⱼ = (y₂ − y₁)³ / (4 y₁ y₂). "
            "Independent of the sidebar channel."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            y1 = number("Upstream depth, y₁ (m)", "j2_y1", 0.4, step=0.05)
        with c2:
            fr = number("Upstream Froude number, Fr₁", "j2_fr", 5.0, step=0.5, fmt_str="%.3f")
        with c3:
            q = number("Total discharge, Q (m³/s), optional", "j2_q", 0.0, minimum=0.0,
                       step=1.0, fmt_str="%.3f",
                       help="Enter Q to get the power dissipated. Leave at 0 to skip.")
        if st.button("Calculate jump", type="primary", width="stretch", key="j2_go"):
            try:
                res = HydraulicJump.rectangular_from_froude(y1, fr, q if q > 0 else None)
                _jump_results(res)
                inputs = {"Upstream depth, y1": fmt(y1, "m"), "Upstream Froude number": fmt(fr, "", 3)}
                if q > 0:
                    inputs["Discharge, Q"] = fmt(q, "m³/s")
                _jump_record("jp_rect", "Hydraulic jump in a rectangular channel",
                             "y2/y1 = 0.5 (sqrt(1 + 8 Fr1^2) - 1)", inputs, res)
            except CATCH as exc:
                show_error(exc)

    # ---------------------------------------------------------- surge
    elif mode == modes[2]:

        st.caption(
            "A surge is a jump that moves, for example after a gate closes "
            "suddenly. Rectangular, horizontal, frictionless channel; set V₂ = 0 "
            "for a gate closed completely."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            y1 = number("Depth before the surge, y₁ (m)", "j3_y1", 1.5)
        with c2:
            v1 = number("Velocity before, V₁ (m/s)", "j3_v1", 2.5)
        with c3:
            v2 = number("Velocity behind, V₂ (m/s)", "j3_v2", 0.0, minimum=0.0)
        if st.button("Calculate surge", type="primary", width="stretch", key="j3_go"):
            try:
                w, y2 = HydraulicJump.surge_speed(y1, v1, v2)
                a, b = st.columns(2)
                a.metric("Surge speed, ω", fmt(w, "m/s"))
                b.metric("Depth behind the surge, y₂", fmt(y2, "m"))
                record("jp_surge", "Moving surge (bore)",
                       "Continuity and momentum across a moving jump",
                       {"Depth before, y1": fmt(y1, "m"), "Velocity before, V1": fmt(v1, "m/s"),
                        "Velocity behind, V2": fmt(v2, "m/s")},
                       {"Surge speed": fmt(w, "m/s"), "Depth behind the surge, y2": fmt(y2, "m")})
            except CATCH as exc:
                show_error(exc)

    # ---------------------------------------------------------- force
    else:

        st.caption(
            "Force on the control volume from F = γ (M₁ − M₂), using the channel "
            "chosen in the sidebar, for example the force on a sluice gate."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            q = number("Discharge, Q (m³/s)", "j4_q", 14.0, step=0.5)
        with c2:
            y1 = number("Depth upstream, y₁ (m)", "j4_y1", 2.0)
        with c3:
            y2 = number("Depth downstream, y₂ (m)", "j4_y2", 0.5)
        if st.button("Calculate force", type="primary", width="stretch", key="j4_go"):
            try:
                m1, m2, force = HydraulicJump.force_on_obstacle(channel, q, y1, y2)
                a, b, c = st.columns(3)
                a.metric("Momentum function, M₁", fmt(m1, "m³"))
                b.metric("Momentum function, M₂", fmt(m2, "m³"))
                c.metric("Force, F", fmt(force, "kN"))
                st.caption("The force acts in the downstream direction."
                           if force >= 0 else "The force acts in the upstream direction.")
                record("jp_force", "Force on a gate or obstacle",
                       "F = gamma (M1 - M2), M = A ybar + Q^2/(g A)",
                       {"Discharge, Q": fmt(q, "m³/s"), "Depth upstream, y1": fmt(y1, "m"),
                        "Depth downstream, y2": fmt(y2, "m")},
                       {"Momentum function, M1": fmt(m1, "m³"), "Momentum function, M2": fmt(m2, "m³"),
                        "Force, F": fmt(force, "kN")}, channel=channel)
            except CATCH as exc:
                show_error(exc)


# ======================================================================
# TAB: WEIRS AND FLUMES
# ======================================================================

def render_weirs():

    st.subheader("Weirs and flumes")
    st.write("Discharge and head for common measuring structures. These tools do "
             "not use the sidebar channel.")

    kinds = [
        "Broad-crested weir",
        "Rectangular sharp-crested weir",
        "V-notch weir",
        "Francis formula (rectangular notch)",
        "Parshall flume",
    ]
    kind = st.selectbox("Structure", kinds, key="wr_kind")
    find = st.radio("Find", ["Discharge from head", "Head from discharge"],
                    horizontal=True, key="wr_find")
    by_head = find.startswith("Discharge")

    contraction_labels = {0: "None (suppressed)", 1: "One end", 2: "Both ends"}
    head_limit = 50.0
    notes = []

    if kind == kinds[0]:
        b = number("Crest width, b (m)", "wr_b0", 2.0)
        cd = number("Discharge coefficient (1.0 for the ideal weir)", "wr_cd0", 1.0, step=0.05)
        function = lambda Y: hx.broad_crested_weir(b, Y, cd)
        formula = "Q = Cd √g (2/3)^(3/2) b Y^(3/2)"
        weir_inputs = {"Crest width, b": fmt(b, "m"), "Cd": fmt(cd, "", 3)}

    elif kind == kinds[1]:
        b = number("Crest length, b (m)", "wr_b1", 1.25)
        crest = number("Crest height above the approach bed, P (m)", "wr_h1", 1.47)
        c1, c2 = st.columns(2)
        with c1:
            method = st.selectbox("Discharge coefficient", list(hx.SHARP_CREST_METHODS),
                                  key="wr_method")
        with c2:
            contractions = st.selectbox("End contractions", [0, 1, 2],
                                        format_func=contraction_labels.get, key="wr_ec")
        cd_manual = number("Cd", "wr_cd1", 0.62, step=0.01) if method == "User-specified" else None
        function = lambda Y: hx.sharp_crested_weir(b, Y, crest, method, cd_manual, contractions)
        formula = "Q = (2/3) Cd √(2g) L_eff H^(3/2),  L_eff = b − 0.1 n H"
        weir_inputs = {
            "Crest length, b": fmt(b, "m"), "Crest height, P": fmt(crest, "m"),
            "Discharge coefficient": method if cd_manual is None else fmt(cd_manual, "", 3),
            "End contractions": contraction_labels[contractions],
        }
        notes.append("Free flow with an aerated nappe is assumed. Very small heads "
                     "(a few centimetres) are affected by surface tension and viscosity.")

    elif kind == kinds[2]:
        theta = number("Notch angle, θ (degrees)", "wr_th", 90.0, step=5.0, fmt_str="%.1f")
        cd = number("Discharge coefficient, Cd (about 0.58 for 90°)", "wr_cd2", 0.58, step=0.01)
        function = lambda Y: hx.v_notch_weir(theta, Y, cd)
        formula = "Q = (8/15) Cd tan(θ/2) √(2g) Y^(5/2)"
        weir_inputs = {"Notch angle": fmt(theta, "°", 1), "Cd": fmt(cd, "", 3)}

    elif kind == kinds[3]:
        length = number("Crest length, L (m)", "wr_l3", 2.0)
        contractions = st.selectbox("End contractions", [0, 1, 2], index=2,
                                    format_func=contraction_labels.get, key="wr_ec3")
        function = lambda Y: hx.francis_weir(length, Y, contractions)
        formula = "Q = 1.84 (L − 0.1 n H) H^(3/2)   (SI units, n = end contractions)"
        weir_inputs = {"Crest length, L": fmt(length, "m"),
                       "End contractions": contraction_labels[contractions]}

    else:
        throat = number("Throat width, B (m)", "wr_b4", 0.5, step=0.1)
        function = lambda Y: hx.parshall_flume(throat, Y)
        formula = "Q = 4 B H^(1.522 B^0.026)   (feet and cfs; converted to SI here)"
        weir_inputs = {"Throat width, B": fmt(throat, "m")}
        head_limit = 5.0
        if not 0.3 <= throat <= 2.4:
            st.warning("The formula applies to throat widths of about 0.3 m to 2.4 m.")

    label = "Head above the crest, Y (m)" if kind != kinds[4] else "Upstream depth, H (m)"
    short = "Head above the crest, Y" if kind != kinds[4] else "Upstream depth, H"
    if by_head:
        head_in = number(label, "wr_y_in", 0.35, step=0.05)
    else:
        q_in = number("Discharge, Q (m³/s)", "wr_q_in", 0.45, step=0.05)

    if st.button("Calculate", type="primary", width="stretch", key="wr_go"):
        try:
            if by_head:
                head = head_in
                q_out = function(head)
            else:
                head = hx.head_for_discharge(function, q_in, hi=head_limit)
                q_out = q_in
            a, b_col = st.columns(2)
            a.metric("Discharge, Q", fmt(q_out, "m³/s"))
            b_col.metric(short, fmt(head, "m"))
            st.caption(formula)

            results = {short: fmt(head, "m"), "Discharge, Q": fmt(q_out, "m³/s")}
            if kind == kinds[1]:
                if cd_manual is None:
                    used = hx.sharp_crested_cd(head, crest, method)
                    results["Discharge coefficient used"] = fmt(used, "", 4)
                    st.write(f"Discharge coefficient at this head: **{used:.4f}** ({method}).")
                if method.startswith("Kindsvater"):
                    st.caption("The head is increased by 1 mm in this method.")
            if kind == kinds[2]:
                coefficient = q_out / head ** 2.5
                results["Q / Y^(5/2)"] = fmt(coefficient, "", 3)
                st.write(f"For this notch, Q = **{coefficient:.3f}** Y^(5/2).")
            for text in notes:
                st.caption(text)
            record("wr_weir", kind, formula.replace("√", "sqrt").replace("θ", "theta"),
                   weir_inputs, results)
        except CATCH as exc:
            show_error(exc)
