
from __future__ import annotations

import math
import matplotlib.pyplot as plt
import streamlit as st

from channel_diagrams import draw_channel
from pdf_report import create_pdf_report

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
      .block-container {
          padding-top: 1.7rem;
          padding-bottom: 2.5rem;
          max-width: 1400px;
      }

      [data-testid="stMetric"] {
          background: var(--secondary-background-color);
          border: 1px solid rgba(128,128,128,.18);
          padding: 14px 16px;
          border-radius: 12px;
      }

      .hero {
          padding: 1.35rem 1.5rem;
          border: 1px solid rgba(128,128,128,.22);
          border-radius: 18px;
          background: linear-gradient(
              120deg,
              rgba(26,95,122,.13),
              rgba(26,95,122,.025)
          );
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
            value=1.0,
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

tab_geometry, tab_manning, tab_critical, tab_curve, tab_report = st.tabs(
    [
        "Section geometry",
        "Manning flow",
        "Critical flow",
        "Discharge-depth curve",
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

    if isinstance(channel, CircularChannel) and depth >= channel.D:

        st.warning(
            f"For this open-channel diagram, depth must be less "
            f"than the pipe diameter ({channel.D:.4f} m)."
        )

    else:

        try:

            p = channel.properties(depth)

            st.subheader("Channel cross-section diagram")

            fig = make_channel_diagram(channel, depth)

            st.pyplot(fig, width="stretch")
            plt.close(fig)

            st.subheader("Hydraulic properties")

            cards = st.columns(5)

            cards[0].metric("Area, A", fmt(p["A"], "m²"))
            cards[1].metric("Wetted perimeter, P", fmt(p["P"], "m"))
            cards[2].metric("Top width, B", fmt(p["B"], "m"))
            cards[3].metric("Hydraulic radius, R", fmt(p["R"], "m"))
            cards[4].metric("Hydraulic depth, Dₕ", fmt(p["D_h"], "m"))

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

        if st.button(
            "Calculate discharge and velocity",
            type="primary",
            width="stretch"
        ):

            try:

                q = Manning.discharge(channel, y, n_value, slope)
                v = Manning.velocity(channel, y, n_value, slope)

                st.session_state["manning_report_results"] = {
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

        if st.button(
            "Calculate normal depth",
            type="primary",
            width="stretch"
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

    actual_y = st.number_input(
        "Actual flow depth, y (m)",
        min_value=0.0001,
        value=1.0,
        step=0.1,
        format="%.4f",
        key="critical_y"
    )

    if st.button(
        "Analyse critical flow",
        type="primary",
        width="stretch"
    ):

        try:

            yc = CriticalFlow.critical_depth(channel, q_critical)

            ec = CriticalFlow.specific_energy(
                channel,
                yc,
                q_critical
            )

            froude = CriticalFlow.froude_number(
                channel,
                actual_y,
                q_critical
            )

            energy = CriticalFlow.specific_energy(
                channel,
                actual_y,
                q_critical
            )

            regime = (
                "Supercritical"
                if froude > 1 + 1e-6
                else "Subcritical"
                if froude < 1 - 1e-6
                else "Critical"
            )

            st.session_state["critical_report_results"] = {
                "Discharge, Q": f"{q_critical:.4f} m³/s",
                "Actual flow depth": f"{actual_y:.4f} m",
                "Critical depth, yc": f"{yc:.4f} m",
                "Minimum specific energy, Ec": f"{ec:.4f} m",
                "Froude number, Fr": f"{froude:.4f}",
                "Flow regime": regime,
                "Specific energy at actual depth": f"{energy:.4f} m",
                "_channel_signature": channel_signature(channel),
            }

            c1, c2, c3 = st.columns(3)

            c1.metric("Critical depth, y꜀", fmt(yc, "m"))
            c2.metric("Minimum specific energy, E꜀", fmt(ec, "m"))
            c3.metric("Froude number, Fr", fmt(froude))

            st.info(
                f"Flow regime at the actual depth: **{regime}**"
            )

            st.metric(
                "Specific energy at actual depth",
                fmt(energy, "m")
            )

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

    if st.button(
        "Generate curve",
        type="primary",
        width="stretch"
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


# ==========================================================
# TAB 5: PDF ENGINEERING REPORT
# ==========================================================

with tab_report:

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
        and report_depth >= channel.D
    ):

        st.warning(
            "For an open-channel report, flow depth must be less "
            "than the pipe diameter."
        )

    else:

        if st.button(
            "Generate PDF Engineering Report",
            type="primary",
            width="stretch",
            key="generate_pdf_report"
        ):

            report_fig = None

            try:

                if not project_name.strip():
                    raise ValueError(
                        "Please enter the project name."
                    )

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
                    prepared_by=prepared_by.strip(),
                    channel=channel,
                    depth=report_depth,
                    geometry=report_geometry,
                    diagram_figure=report_fig,
                    manning_results=manning_results,
                    critical_results=critical_results,
                    engineering_notes=engineering_notes
                )

                # Save generated PDF in Streamlit session state.
                st.session_state["generated_pdf_report"] = pdf_bytes

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
    if st.session_state.get("generated_pdf_report"):

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
