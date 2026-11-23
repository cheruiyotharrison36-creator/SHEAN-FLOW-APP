from __future__ import annotations
import math
import hashlib
import matplotlib.pyplot as plt
import streamlit as st
from channel_diagrams import draw_channel
from pdf_report import create_pdf_report
from hydraulic_structures import (rectangular_hydraulic_jump, sharp_crested_rectangular_weir, v_notch_weir, trapezoidal_weir)
from compact_report import make_compact_report
from design_tools import preliminary_rectangular_design, convert_length, convert_discharge
from open_channel_program_fixed import (
    RectangularChannel,
    TrapezoidalChannel,
    TriangularChannel,
    CircularChannel,
    Manning,
    CriticalFlow,
    MANNINGS_N,
)
# ---------- Page configuration ----------
st.set_page_config(
    page_title="SHEAN FLOW APP",
    page_icon="〰️",
    layout="wide",
    initial_sidebar_state="expanded",
)
# ---------- Styling ----------
st.markdown(
    """
    <style>
      /* SF-014: Streamlit theme tokens follow Light/Dark appearance. */
      .block-container {
          padding-top: 1.7rem;
          padding-bottom: 2.5rem;
          max-width: 1400px;
      }
      [data-testid="stMetric"] {
          background: var(--secondary-background-color);
          border: 1px solid var(--secondary-background-color);
          padding: 14px 16px;
          border-radius: 12px;
      }
      .hero {
          padding: 1.35rem 1.5rem;
          border: 1px solid var(--secondary-background-color);
          border-radius: 18px;
          background: var(--secondary-background-color);
          margin-bottom: 1.2rem;
      }
      .hero-kicker {
          font-size: .78rem;
          letter-spacing: .12em;
          text-transform: uppercase;
          color: var(--secondary-text-color);
          font-weight: 700;
      }
      .hero h1 {
          margin: .25rem 0 .35rem 0;
          font-size: clamp(1.65rem, 3vw, 2.35rem);
      }
      .hero p {
          margin: 0;
          color: var(--secondary-text-color);
      }
      div[data-testid="stTabs"] button {
          font-weight: 600;
      }
      .small-note {
          font-size: .85rem;
          color: var(--secondary-text-color);
      }
    </style>
    """,
    unsafe_allow_html=True,
)
# ---------- Application heading ----------
st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">
          Hydraulic engineering • Calculation workspace
      </div>
      <h1>SHEAN FLOW APP</h1>
      <p>
          Non-erodible channel design, geometry, Manning uniform flow,
          critical flow and discharge-depth analysis.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
# ---------- Session state ----------
if "manning_report_results" not in st.session_state:
    st.session_state["manning_report_results"] = None
if "critical_report_results" not in st.session_state:
    st.session_state["critical_report_results"] = None
# ---------- Sidebar: Channel setup ----------
st.sidebar.title("Channel setup")
st.sidebar.caption("Choose a section and enter its dimensions.")
channel_type = st.sidebar.selectbox(
    "Channel shape",
    ["Rectangular", "Trapezoidal", "Triangular", "Circular"],
)
channel = None
try:
    if channel_type == "Rectangular":
        b = st.sidebar.number_input(
            "Bottom width, b (m)",
            min_value=0.001,
            value=2.0,
            step=0.1,
            format="%.3f"
        )
        channel = RectangularChannel(b=b)
    elif channel_type == "Trapezoidal":
        b = st.sidebar.number_input(
            "Bottom width, b (m)",
            min_value=0.001,
            value=2.0,
            step=0.1,
            format="%.3f"
        )
        left = st.sidebar.number_input(
            "Left side slope, m (H:V)",
            min_value=0.0,
            value=1.0,
            step=0.1,
            format="%.3f"
        )
        right = st.sidebar.number_input(
            "Right side slope, n (H:V)",
            min_value=0.0,
            value=1.0,
            step=0.1,
            format="%.3f"
        )
        if left + right <= 0:
            st.sidebar.error(
                "At least one side slope must be greater than zero."
            )
        else:
            channel = TrapezoidalChannel(
                b=b,
                m=left,
                n=right
            )
    elif channel_type == "Triangular":
        left = st.sidebar.number_input(
            "Left side slope, m (H:V)",
            min_value=0.0,
            value=1.0,
            step=0.1,
            format="%.3f"
        )
        right = st.sidebar.number_input(
            "Right side slope, n (H:V)",
            min_value=0.0,
            value=1.0,
            step=0.1,
            format="%.3f"
        )
        if left + right <= 0:
            st.sidebar.error(
                "At least one side slope must be greater than zero."
            )
        else:
            channel = TriangularChannel(
                m=left,
                n=right
            )
    else:
        diameter = st.sidebar.number_input(
            "Pipe diameter, D (m)",
            min_value=0.001,
            value=2.0,
            step=0.1,
            format="%.3f"
        )
        channel = CircularChannel(D=diameter)
except ValueError as exc:
    st.sidebar.error(str(exc))
st.sidebar.divider()
st.sidebar.markdown("**Unit convention**")
st.sidebar.caption(
    "Enter dimensions in metres, discharge in m³/s, "
    "slope in m/m and Manning's n as a dimensionless coefficient."
)
if channel is None:
    st.warning(
        "Complete the channel dimensions in the sidebar "
        "to use the calculator."
    )
    st.stop()
st.caption(f"Active section: **{channel.name} channel**")
st.sidebar.divider()
st.sidebar.subheader("Project context")
project_reference = st.sidebar.text_input("Project reference (optional)", key="project_reference")
st.sidebar.caption("Record a project reference for traceability; verify site conditions independently.")

# ---------- SF-002: Explicit input review ----------
st.sidebar.info(
    "Example values are provided for demonstration only. "
    "Review project-specific dimensions and assumptions before calculating."
)


def confirm_inputs(workflow: str, values: tuple) -> bool:
    """Require fresh acknowledgement for each distinct set of inputs."""
    signature = hashlib.sha256(repr(values).encode("utf-8")).hexdigest()[:20]
    st.caption("Prefilled values are examples, not approved engineering inputs.")
    return st.checkbox(
        "I have reviewed these inputs and confirm they are appropriate "
        "for this calculation.",
        value=False,
        key=f"sf002_confirm_{workflow}_{signature}",
    )


# ---------- Shared helper functions ----------
def show_error(exc: Exception) -> None:
    st.error(str(exc))
def fmt(value: float, unit: str = "") -> str:
    if not math.isfinite(value):
        return "—"
    return f"{value:,.4f}{(' ' + unit) if unit else ''}"
def roughness_controls(key: str):
    materials = list(MANNINGS_N.keys())
    material = st.selectbox(
        "Channel lining / material",
        materials,
        index=2,
        key=f"{key}_material"
    )
    default_n = MANNINGS_N[material]
    col1, col2 = st.columns(2)
    with col1:
        n_value = st.number_input(
            "Manning's roughness, n",
            min_value=0.0001,
            value=float(default_n),
            step=0.001,
            format="%.4f",
            key=f"{key}_n"
        )
    with col2:
        slope = st.number_input(
            "Bed slope, S₀ (m/m)",
            min_value=0.000001,
            value=0.001,
            step=0.0001,
            format="%.6f",
            key=f"{key}_slope"
        )
    return n_value, slope
def channel_signature(channel):
    values = [type(channel).__name__]
    for attribute in ("b", "m", "n", "D"):
        if hasattr(channel, attribute):
            values.append(
                (attribute, float(getattr(channel, attribute)))
            )
    return tuple(values)
def make_channel_diagram(channel, depth):
    if isinstance(channel, RectangularChannel):
        return draw_channel(
            shape="rectangular",
            depth=depth,
            bottom_width=channel.b
        )
    elif isinstance(channel, TrapezoidalChannel):
        return draw_channel(
            shape="trapezoidal",
            depth=depth,
            bottom_width=channel.b,
            side_slope=channel.m,
            right_side_slope=channel.n
        )
    elif isinstance(channel, TriangularChannel):
        return draw_channel(
            shape="triangular",
            depth=depth,
            side_slope=channel.m,
            right_side_slope=channel.n
        )
    elif isinstance(channel, CircularChannel):
        return draw_channel(
            shape="circular",
            depth=depth,
            diameter=channel.D
        )
    raise ValueError("Unsupported channel shape.")
def report_results_for_current_channel(session_key):
    results = st.session_state.get(session_key)
    if not results:
        return None
    if results.get("_channel_signature") != channel_signature(channel):
        return None
    return {
        key: value
        for key, value in results.items()
        if key != "_channel_signature"
    }
# ---------- Main workspace ----------
tab_geometry, tab_manning, tab_critical, tab_curve, tab_jump, tab_weirs, tab_design, tab_report = st.tabs(
    [
        "Section geometry",
        "Manning flow",
        "Critical flow",
        "Discharge-depth curve",
        "Hydraulic jump",
        "Weirs",
        "Preliminary design & units",
        "PDF Engineering Report"
    ]
)
# ==========================================================
# TAB 1: SECTION GEOMETRY AND CHANNEL DIAGRAMS
# ==========================================================
with tab_geometry:
    st.subheader("Channel geometry")
    st.write(
        "Calculate the geometric and hydraulic properties "
        "at a selected flow depth."
    )
    depth = st.number_input(
        "Flow depth, y (m)",
        min_value=0.0001,
        value=1.0,
        step=0.1,
        format="%.4f",
        key="geometry_depth"
    )
    st.caption(
        "Input validation: flow depth must be at least 0.0001 m. "
        "If an entry is rejected by the input widget, the application may "
        "continue to show results for the last accepted value. "
        "Correct the entry and verify the accepted depth before using results."
    )
    geometry_confirmed = confirm_inputs("geometry", (channel_signature(channel), depth))
    if not geometry_confirmed:
        st.info("Confirm the geometry inputs above to display calculated results.")
    elif isinstance(channel, CircularChannel) and depth > channel.D:
        st.warning(
            f"For a circular section, depth cannot exceed "
            f"the pipe diameter ({channel.D:.4f} m)."
        )
    elif geometry_confirmed:
        try:
            p = channel.properties(depth)
            st.subheader("Channel cross-section diagram")
            fig = make_channel_diagram(channel, depth)
            st.pyplot(fig, width="stretch")
            plt.close(fig)
            st.subheader("Hydraulic properties")
            st.info(
                f"**Results calculated for accepted flow depth y = {depth:.4f} m** "
                f"and the currently selected {channel.name.lower()} section. "
                "An invalid or uncommitted entry in the depth field is not "
                "used for these results."
            )
            # SF-012: readable, wrapping text instead of five narrow metric cards.
            # Keep the complete four-decimal value and its unit together.
            geometry_values = (
                ("Area, A", fmt(p["A"], "m²")),
                ("Wetted perimeter, P", fmt(p["P"], "m")),
                ("Top width, B", fmt(p["B"], "m")),
                ("Hydraulic radius, R", fmt(p["R"], "m")),
                ("Hydraulic depth, Dₕ", fmt(p["D_h"], "m")),
            )
            for row_start in range(0, len(geometry_values), 2):
                columns = st.columns(2)
                for column, (label, value) in zip(
                    columns, geometry_values[row_start:row_start + 2]
                ):
                    with column:
                        with st.container(border=True):
                            st.markdown(f"**{label}**")
                            st.write(value)
            st.success("Geometry calculated successfully.")
        except (ValueError, ZeroDivisionError, AttributeError) as exc:
            show_error(exc)
# ==========================================================
# TAB 2: MANNING FLOW
# ==========================================================
with tab_manning:
    st.subheader("Manning's equation")
    st.write(
        "Determine discharge and velocity from depth, "
        "or estimate normal depth from a known discharge."
    )
    n_value, slope = roughness_controls("manning")
    mode = st.radio(
        "Calculation",
        [
            "Discharge and velocity from depth",
            "Normal depth from discharge"
        ],
        horizontal=True
    )
    if mode == "Discharge and velocity from depth":
        y = st.number_input(
            "Flow depth, y (m)",
            min_value=0.0001,
            value=1.0,
            step=0.1,
            format="%.4f",
            key="manning_y"
        )
        manning_confirmed = confirm_inputs("manning_discharge", (channel_signature(channel), y, n_value, slope))
        if st.button(
            "Calculate discharge and velocity",
            type="primary",
            width="stretch",
            disabled=not manning_confirmed,
        ):
            try:
                q = Manning.discharge(channel, y, n_value, slope)
                v = Manning.velocity(channel, y, n_value, slope)
                st.session_state["manning_report_results"] = {
                    "Input review": "Confirmed by user",
                    "Calculation type": "Discharge and velocity from depth",
                    "Flow depth": f"{y:.4f} m",
                    "Manning roughness, n": f"{n_value:.4f}",
                    "Bed slope, S0": f"{slope:.6f}",
                    "Discharge, Q": f"{q:.4f} m³/s",
                    "Mean velocity, V": f"{v:.4f} m/s",
                    "_channel_signature": channel_signature(channel),
                }
                a, b = st.columns(2)
                a.metric("Discharge, Q", fmt(q, "m³/s"))
                b.metric("Mean velocity, V", fmt(v, "m/s"))
                with st.expander("Calculation details"):
                    props = channel.properties(y)
                    st.write(f"Flow area, A = {props['A']:.6f} m²")
                    st.write(f"Hydraulic radius, R = {props['R']:.6f} m")
                    st.latex(
                        r"Q = \frac{1}{n} A R^{2/3} S_0^{1/2}"
                    )
                    st.latex(
                        r"V = \frac{1}{n} R^{2/3} S_0^{1/2}"
                    )
            except (
                ValueError,
                ZeroDivisionError,
                OverflowError
            ) as exc:
                show_error(exc)
    else:
        q_design = st.number_input(
            "Design discharge, Q (m³/s)",
            min_value=0.0001,
            value=2.0,
            step=0.1,
            format="%.4f",
            key="normal_q"
        )
        normal_confirmed = confirm_inputs("manning_normal", (channel_signature(channel), q_design, n_value, slope))
        if st.button(
            "Calculate normal depth",
            type="primary",
            width="stretch",
            disabled=not normal_confirmed,
        ):
            try:
                y0 = Manning.normal_depth(
                    channel,
                    q_design,
                    n_value,
                    slope
                )
                v = q_design / channel.area(y0)
                st.session_state["manning_report_results"] = {
                    "Input review": "Confirmed by user",
                    "Calculation type": "Normal depth from discharge",
                    "Design discharge, Q": f"{q_design:.4f} m³/s",
                    "Manning roughness, n": f"{n_value:.4f}",
                    "Bed slope, S0": f"{slope:.6f}",
                    "Normal depth, y0": f"{y0:.4f} m",
                    "Mean velocity, V": f"{v:.4f} m/s",
                    "_channel_signature": channel_signature(channel),
                }
                st.metric("Normal depth, y₀", fmt(y0, "m"))
                st.metric("Mean velocity, V", fmt(v, "m/s"))
                st.caption(
                    "The solver searches from shallow to deeper "
                    "flow and returns the first bracketed solution."
                )
            except (
                ValueError,
                ZeroDivisionError,
                OverflowError
            ) as exc:
                show_error(exc)
# ==========================================================
# TAB 3: CRITICAL FLOW
# ==========================================================
with tab_critical:
    st.subheader("Critical flow analysis")
    st.write(
        "Calculate critical depth, minimum specific energy, "
        "Froude number and flow regime."
    )
    q_critical = st.number_input(
        "Discharge, Q (m³/s)",
        min_value=0.0001,
        value=2.0,
        step=0.1,
        format="%.4f",
        key="critical_q"
    )
    evaluate_actual_depth = st.checkbox(
        "Also evaluate flow regime at a specified actual depth",
        value=False,
        key="critical_evaluate_actual",
    )
    actual_y = None
    if evaluate_actual_depth:
        actual_y = st.number_input(
            "Actual flow depth, y (m)",
            min_value=0.0001, value=1.0, step=0.1,
            format="%.4f", key="critical_y",
        )
    critical_confirmed = confirm_inputs("critical", (channel_signature(channel), q_critical, actual_y))
    if st.button(
        "Analyse critical flow",
        type="primary",
        width="stretch",
        disabled=not critical_confirmed,
    ):
        try:
            yc = CriticalFlow.critical_depth(channel, q_critical)
            ec = CriticalFlow.specific_energy(
                channel,
                yc,
                q_critical
            )
            report = {
                "Input review": "Confirmed by user",
                "Discharge, Q": f"{q_critical:.4f} m³/s",
                "Critical depth, yc": f"{yc:.4f} m",
                "Minimum specific energy, Ec": f"{ec:.4f} m",
                "_channel_signature": channel_signature(channel),
            }
            c1, c2 = st.columns(2)
            c1.metric("Critical depth, y꜀", fmt(yc, "m"))
            c2.metric("Minimum specific energy, E꜀", fmt(ec, "m"))
            if evaluate_actual_depth:
                froude = CriticalFlow.froude_number(channel, actual_y, q_critical)
                energy = CriticalFlow.specific_energy(channel, actual_y, q_critical)
                regime = (
                    "Supercritical" if froude > 1 + 1e-6 else
                    "Subcritical" if froude < 1 - 1e-6 else "Critical"
                )
                report.update({
                    "Actual flow depth": f"{actual_y:.4f} m",
                    "Froude number, Fr": f"{froude:.4f}",
                    "Flow regime": regime,
                    "Specific energy at actual depth": f"{energy:.4f} m",
                })
                st.metric("Froude number, Fr", fmt(froude))
                st.info(f"Flow regime at the actual depth: **{regime}**")
                st.metric("Specific energy at actual depth", fmt(energy, "m"))
            st.session_state["critical_report_results"] = report
            with st.expander("Equations used"):
                st.latex(r"Fr = \frac{V}{\sqrt{gD_h}}")
                st.latex(r"E = y + \frac{Q^2}{2gA^2}")
                st.latex(
                    r"\frac{Q^2 B}{gA^3} = 1"
                    r"\quad \text{at critical flow}"
                )
        except (
            ValueError,
            ZeroDivisionError,
            OverflowError
        ) as exc:
            show_error(exc)
# ==========================================================
# TAB 4: DISCHARGE-DEPTH CURVE
# ==========================================================
with tab_curve:
    st.subheader("Discharge-depth relationship")
    st.write(
        "Generate a curve showing how discharge varies "
        "with flow depth for the selected section."
    )
    curve_n, curve_slope = roughness_controls("curve")
    if isinstance(channel, CircularChannel):
        max_depth = float(channel.D)
        st.info(
            f"Maximum plotted depth is set to the pipe diameter: "
            f"{max_depth:.4f} m."
        )
    else:
        max_depth = st.number_input(
            "Maximum depth, yₘₐₓ (m)",
            min_value=0.001,
            value=2.0,
            step=0.1,
            format="%.4f",
            key="curve_max_depth"
        )
    points = st.slider(
        "Number of calculation points",
        min_value=50,
        max_value=500,
        value=200,
        step=25
    )
    curve_confirmed = confirm_inputs("curve", (channel_signature(channel), curve_n, curve_slope, max_depth, points))
    if st.button(
        "Generate curve",
        type="primary",
        width="stretch",
        disabled=not curve_confirmed,
    ):
        try:
            ys, qs = Manning.discharge_depth_curve(
                channel,
                curve_n,
                curve_slope,
                max_depth,
                num_points=points
            )
            peak_index = max(
                range(len(qs)),
                key=qs.__getitem__
            )
            st.metric(
                "Maximum sampled discharge",
                fmt(qs[peak_index], "m³/s")
            )
            st.metric(
                "Depth at maximum sampled discharge",
                fmt(ys[peak_index], "m")
            )
            fig, ax = plt.subplots(figsize=(9, 4.6))
            ax.plot(qs, ys, linewidth=2.4)
            ax.set_xlabel("Discharge, Q (m³/s)")
            ax.set_ylabel("Flow depth, y (m)")
            ax.set_title(
                f"Discharge-Depth Curve — {channel.name} Channel"
            )
            ax.grid(True, alpha=0.28)
            fig.tight_layout()
            st.pyplot(fig, width="stretch")
            plt.close(fig)
            with st.expander("View sampled values"):
                st.dataframe(
                    {
                        "Depth y (m)": ys,
                        "Discharge Q (m³/s)": qs
                    },
                    width="stretch",
                    hide_index=True
                )
        except (
            ValueError,
            ZeroDivisionError,
            OverflowError
        ) as exc:
            show_error(exc)
# Hydraulic jump and weir calculations
with tab_jump:
    st.subheader("Rectangular hydraulic jump")
    st.caption("Horizontal rectangular channel; steady flow and negligible external forces. Supercritical approach flow is required.")
    if True:
        j_q = st.number_input("Discharge (m³/s)", min_value=0.000001, value=5.0, format="%.5f")
        j_b = st.number_input("Channel width (m)", min_value=0.000001, value=2.0, format="%.4f")
        j_y = st.number_input("Upstream depth (m)", min_value=0.000001, value=0.4, format="%.4f")
        jump_confirmed = confirm_inputs("jump", (j_q, j_b, j_y))
        run_jump = st.button("Calculate hydraulic jump", type="primary", disabled=not jump_confirmed)
    if run_jump:
        try:
            result = rectangular_hydraulic_jump(j_q, j_b, j_y)
            st.session_state["structure_report"] = {"title": "Rectangular hydraulic jump" + (f" — {project_reference}" if project_reference else ""), "inputs": {"Input review": "Confirmed by user", "Discharge": f"{j_q:.4f} m³/s", "Channel width": f"{j_b:.4f} m", "Upstream depth": f"{j_y:.4f} m"}, "results": {"Sequent depth": f"{result.downstream_depth:.4f} m", "Upstream Froude": f"{result.upstream_froude:.3f}", "Downstream Froude": f"{result.downstream_froude:.3f}", "Energy loss": f"{result.energy_loss:.4f} m", "Jump classification": result.classification}, "formula": "y2/y1 = (sqrt(1 + 8 Fr1²) - 1)/2"}
            a,b,c = st.columns(3)
            a.metric("Sequent depth", f"{result.downstream_depth:.4f} m")
            b.metric("Energy loss", f"{result.energy_loss:.4f} m")
            c.metric("Jump type", result.classification)
            st.write(f"Upstream Fr: **{result.upstream_froude:.3f}** · Downstream Fr: **{result.downstream_froude:.3f}**")
        except (ValueError, OverflowError) as exc:
            st.error(str(exc))
with tab_weirs:
    st.subheader("Free-flow weir discharge")
    st.caption(
        "Idealized sharp-crested notch equations. Verify crest geometry, "
        "coefficient calibration, approach conditions and absence of "
        "submergence before design use."
    )

    # Outside the form so changing configuration immediately updates the fields.
    w_type = st.selectbox(
        "Weir configuration",
        ["Rectangular", "V-notch (triangular)", "Trapezoidal"],
        key="weir_configuration",
    )

    if True:
        w_head = st.number_input(
            "Head above crest (m)", min_value=0.000001,
            value=0.3, format="%.4f", key="weir_head",
        )

        # Fields not applicable to the chosen weir are not shown or used.
        w_width = None
        w_angle = None
        w_side = None

        if w_type == "Rectangular":
            w_width = st.number_input(
                "Crest width (m)", min_value=0.000001,
                value=1.0, key="weir_rect_width",
            )
        elif w_type == "V-notch (triangular)":
            w_angle = st.number_input(
                "V-notch included angle (degrees)",
                min_value=0.1, max_value=179.9, value=90.0,
                key="weir_notch_angle",
            )
        else:
            w_width = st.number_input(
                "Bottom width (m)", min_value=0.000001,
                value=1.0, key="weir_trap_width",
            )
            w_side = st.number_input(
                "Trapezoidal side slope (horizontal : vertical)",
                min_value=0.0, value=0.25, key="weir_trap_side",
            )

        w_cd = st.number_input(
            "Discharge coefficient, Cd", min_value=0.001,
            max_value=1.0, value=0.62, format="%.3f", key="weir_cd",
        )
        st.warning(
            "This is an idealized free-flow sharp-crested weir model. "
            "It does not account for submergence, crest contractions, "
            "installation-specific coefficient calibration or approach-flow effects "
            "(except where explicitly supported by the calculation function)."
        )
        free_flow_confirmed = st.checkbox(
            "I confirm free discharge (no downstream submergence), a sharp crest, "
            "and an appropriate site-specific discharge coefficient.",
            value=False,
            key=f"weir_applicability_{hashlib.sha256(repr((w_type, w_head, w_width, w_angle, w_side, w_cd)).encode()).hexdigest()[:20]}",
        )
        weir_confirmed = confirm_inputs("weir", (w_type, w_head, w_width, w_angle, w_side, w_cd)) and free_flow_confirmed
        run_weir = st.button("Calculate discharge", type="primary", disabled=not weir_confirmed)

    if run_weir:
        try:
            if w_type == "Rectangular":
                discharge = sharp_crested_rectangular_weir(w_head, w_width, w_cd)
                formula = "Q = (2/3) Cd b sqrt(2g) H^(3/2)"
            elif w_type == "V-notch (triangular)":
                discharge = v_notch_weir(w_head, w_angle, w_cd)
                formula = "Q = (8/15) Cd tan(theta/2) sqrt(2g) H^(5/2)"
            else:
                discharge = trapezoidal_weir(w_head, w_width, w_side, w_cd)
                formula = "Q = Cd sqrt(2g) [(2/3)bH^(3/2) + (8/15)zH^(5/2)]"

            st.metric("Calculated discharge", f"{discharge:.5f} m³/s")
            st.code(formula, language=None)
            inputs = {
                "Input review": "Confirmed by user",
                "Applicability": "User confirmed idealized free-flow assumptions",
                "Head": f"{w_head:.4f} m",
                "Discharge coefficient": f"{w_cd:.3f}",
            }
            if w_type == "Rectangular":
                inputs["Crest width"] = f"{w_width:.4f} m"
            elif w_type == "V-notch (triangular)":
                inputs["Notch angle"] = f"{w_angle:.1f} degrees"
            else:
                inputs["Bottom width"] = f"{w_width:.4f} m"
                inputs["Side slope"] = f"{w_side:.3f} H:1V"
            st.session_state["structure_report"] = {
                "title": w_type + " weir" + (f" — {project_reference}" if project_reference else ""),
                "inputs": inputs,
                "results": {"Discharge": f"{discharge:.5f} m³/s"},
                "formula": formula,
            }
        except (ValueError, OverflowError) as exc:
            st.error(str(exc))

# ==========================================================
# PRELIMINARY DESIGN AND UNIT CONVERSION (SF-008/SF-010)
# ==========================================================
with tab_design:
    st.subheader("Preliminary rectangular channel sizing")
    st.warning(
        "Uniform-flow sizing only. Not a completed engineering design: "
        "verify erosion, sediment, lining, freeboard criteria, hydraulic grade, "
        "transitions, flood risk and applicable project standards."
    )
    d_q = st.number_input("Design discharge (m³/s)", min_value=0.000001, value=4.5, key="design_q")
    d_b = st.number_input("Proposed bottom width (m)", min_value=0.001, value=2.4, key="design_b")
    d_n = st.number_input("Design Manning n", min_value=0.0001, value=0.015, format="%.4f", key="design_n")
    d_s = st.number_input("Design bed slope (m/m)", min_value=0.000001, value=0.001, format="%.6f", key="design_s")
    d_fb = st.number_input("Proposed freeboard (m)", min_value=0.0, value=0.3, key="design_fb")
    d_confirm = confirm_inputs("preliminary_design", (d_q, d_b, d_n, d_s, d_fb))
    if st.button("Calculate preliminary dimensions", disabled=not d_confirm, type="primary"):
        try:
            design = preliminary_rectangular_design(d_q, d_b, d_n, d_s, d_fb)
            st.metric("Normal flow depth", fmt(design["normal_depth_m"], "m"))
            st.metric("Mean velocity", fmt(design["mean_velocity_m_s"], "m/s"))
            st.metric("Preliminary wall height", fmt(design["minimum_wall_height_m"], "m"))
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            st.error(str(exc))
    st.divider()
    st.subheader("SI / US customary unit conversion")
    st.caption("Core hydraulic calculations remain SI. Convert external data before entry; do not mix unit systems.")
    conversion = st.selectbox("Conversion", ["Metres to feet", "Feet to metres", "m³/s to ft³/s", "ft³/s to m³/s"])
    conversion_value = st.number_input("Value to convert", value=1.0, key="conversion_value")
    if conversion == "Metres to feet":
        converted, unit = convert_length(conversion_value, "ft"), "ft"
    elif conversion == "Feet to metres":
        converted, unit = convert_length(conversion_value, "m"), "m"
    elif conversion == "m³/s to ft³/s":
        converted, unit = convert_discharge(conversion_value, "cfs"), "ft³/s"
    else:
        converted, unit = convert_discharge(conversion_value, "cms"), "m³/s"
    st.metric("Converted value", f"{converted:.6g} {unit}")

# ==========================================================
# TAB 5: PDF ENGINEERING REPORT
# ==========================================================
with tab_report:
    st.markdown("#### Concise calculation report")
    latest = st.session_state.get("structure_report")
    if latest:
        st.caption("Latest hydraulic jump or weir calculation")
        st.write(f"**{latest['title']}**")
        st.download_button("Download concise calculation PDF", make_compact_report(latest), file_name="SHEAN_Flow_Calculation.pdf", mime="application/pdf", key="compact_pdf")
    else:
        st.info("Run a hydraulic jump or weir calculation to enable a concise, calculation-specific PDF.")
    st.divider()
    st.subheader("Professional PDF Engineering Report")
    st.write(
        "Generate a downloadable engineering report containing "
        "project information, channel dimensions, a cross-section "
        "diagram, hydraulic properties, Manning results and "
        "critical-flow results."
    )
    st.divider()
    st.markdown("#### 1. Project information")
    project_name = st.text_input(
        "Project name",
        placeholder="e.g. Non-Erodible Drainage Channel Design",
        key="report_project_name"
    )
    prepared_by = st.text_input(
        "Prepared by",
        placeholder="Enter your name or organisation",
        key="report_prepared_by"
    )
    st.markdown("#### 2. Report flow conditions")
    report_depth = st.number_input(
        "Flow depth for report, y (m)",
        min_value=0.0001,
        value=1.0,
        step=0.1,
        format="%.4f",
        key="report_depth"
    )
    engineering_notes = st.text_area(
        "Engineering notes / observations",
        placeholder=(
            "Enter project observations, design assumptions, "
            "recommendations or other relevant engineering notes."
        ),
        height=120,
        key="report_notes"
    )
    report_revision = st.text_input(
        "Document revision", value="A", key="report_revision",
        help="Enter the current document revision (for example A, B or 01).",
    )
    st.caption("Project reference from the sidebar will be included in the PDF.")
    report_confirmed = confirm_inputs(
        "engineering_report",
        (channel_signature(channel), project_reference, project_name, prepared_by, report_revision, report_depth, engineering_notes),
    )
    st.divider()
    st.markdown("#### 3. Calculation results available")
    manning_preview = report_results_for_current_channel(
        "manning_report_results"
    )
    critical_preview = report_results_for_current_channel(
        "critical_report_results"
    )
    if manning_preview:
        st.success(
            "A Manning calculation is available for the current channel."
        )
    else:
        st.info(
            "No matching Manning result is available yet. "
            "Calculate Manning flow first if you want it in the report."
        )
    if critical_preview:
        st.success(
            "A Critical Flow calculation is available for the current channel."
        )
    else:
        st.info(
            "No matching Critical Flow result is available yet. "
            "Analyse critical flow first if you want it in the report."
        )
    st.divider()
    st.markdown("#### 4. Generate your report")
    st.info(
        "The report will use the channel shape and dimensions "
        "currently selected in the sidebar. It will also include "
        "matching successful Manning and Critical Flow calculations."
    )
    if (
        isinstance(channel, CircularChannel)
        and report_depth > channel.D
    ):
        st.warning(
            "For a circular section, flow depth cannot exceed "
            "the pipe diameter."
        )
    else:
        if st.button(
            "Generate PDF Engineering Report",
            type="primary",
            width="stretch",
            disabled=not report_confirmed,
            key="generate_pdf_report"
        ):
            report_fig = None
            try:
                if not project_name.strip():
                    raise ValueError(
                        "Please enter the project name."
                    )
                if not report_revision.strip():
                    raise ValueError("Please enter a document revision.")
                if not prepared_by.strip():
                    raise ValueError(
                        "Please enter the name of the person preparing the report."
                    )
                # Calculate channel geometry.
                report_geometry = channel.properties(report_depth)
                # Create the channel cross-section diagram.
                report_fig = make_channel_diagram(
                    channel,
                    report_depth
                )
                # Retrieve matching calculation results.
                manning_results = report_results_for_current_channel(
                    "manning_report_results"
                )
                critical_results = report_results_for_current_channel(
                    "critical_report_results"
                )
                # Generate the PDF document.
                pdf_bytes = create_pdf_report(
                    project_name=project_name.strip(),
                    project_reference=project_reference.strip(),
                    document_revision=report_revision.strip(),
                    prepared_by=prepared_by.strip(),
                    channel=channel,
                    depth=report_depth,
                    geometry=report_geometry,
                    diagram_figure=report_fig,
                    manning_results=manning_results,
                    critical_results=critical_results,
                    engineering_notes=("Input review: confirmed by user for this report.\n" + engineering_notes)
                )
                # Save generated PDF in Streamlit session state.
                st.session_state["generated_pdf_report"] = pdf_bytes
                st.session_state["sf002_report_signature"] = repr((channel_signature(channel), project_reference, report_revision, report_depth, project_name, prepared_by, engineering_notes, repr(manning_preview), repr(critical_preview)))
                st.session_state["generated_pdf_filename"] = (
                    "SHEAN_FLOW_Engineering_Report.pdf"
                )
                st.success(
                    "Your engineering report has been generated successfully."
                )
            except (
                ValueError,
                ZeroDivisionError,
                AttributeError,
                TypeError,
                KeyError,
                OSError
            ) as exc:
                st.error(f"Could not generate the PDF report: {exc}")
            except Exception as exc:
                st.error(
                    f"An unexpected error occurred while generating "
                    f"the report: {exc}"
                )
            finally:
                if report_fig is not None:
                    plt.close(report_fig)
    # Display the download button after successful generation.
    if st.session_state.get("generated_pdf_report") and st.session_state.get("sf002_report_signature") == repr((channel_signature(channel), project_reference, report_revision, report_depth, project_name, prepared_by, engineering_notes, repr(manning_preview), repr(critical_preview))):
        st.divider()
        st.success("Your PDF report is ready.")
        st.download_button(
            label="Download PDF Engineering Report",
            data=st.session_state["generated_pdf_report"],
            file_name=st.session_state.get(
                "generated_pdf_filename",
                "SHEAN_FLOW_Engineering_Report.pdf"
            ),
            mime="application/pdf",
            type="primary",
            width="stretch",
            key="download_pdf_report"
        )
# ---------- Footer ----------
st.divider()
st.markdown(
    """
    <div class="small-note">
        SHEAN FLOW APP • Engineering calculation aid • SI units
        • Verify design inputs, assumptions and applicable standards
        before using results for construction.
    </div>
    """,
    unsafe_allow_html=True,
)
