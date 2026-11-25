"""
Shared Streamlit helpers for SHEAN FLOW APP.

    - number formatting and error display
    - common input widgets (numbers, roughness and bed slope)
    - table display
    - the store of finished calculations that can be added to the PDF report
"""
from __future__ import annotations

import math
from io import BytesIO

import streamlit as st

from open_channel import MANNINGS_N
import hydraulic_tools as hx

# Errors raised by the calculation modules for invalid or impossible input.
CATCH = (ValueError, ZeroDivisionError, OverflowError)

# Session-state key under which finished calculations are kept for the report.
REPORT_KEY = "report_items"


# ----------------------------------------------------------------------
# Formatting and messages
# ----------------------------------------------------------------------

def fmt(value, unit: str = "", digits: int = 4) -> str:
    """Format a number with thousands separators, or an em dash if undefined."""
    if value is None or not math.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}{(' ' + unit) if unit else ''}"


def show_error(exc: Exception) -> None:
    st.error(str(exc))


# ----------------------------------------------------------------------
# Input widgets
# ----------------------------------------------------------------------

def number(label, key, value, minimum=0.0001, step=0.1, fmt_str="%.4f", **kwargs):
    """Numeric input with a stable key."""
    return st.number_input(
        label, min_value=minimum, value=value, step=step,
        format=fmt_str, key=key, **kwargs,
    )


def roughness_controls(key: str, default_slope: float = 0.001, allow_flat: bool = False):
    """Lining material, Manning's n and bed slope S0.

    With allow_flat the slope may be zero (horizontal) or negative (adverse).
    Returns (n, S0).
    """
    materials = list(MANNINGS_N.keys())
    material = st.selectbox(
        "Channel lining / material", materials, index=2, key=f"{key}_material"
    )
    col1, col2 = st.columns(2)
    with col1:
        n_value = st.number_input(
            "Manning's roughness, n",
            min_value=0.0001,
            value=float(MANNINGS_N[material]),
            step=0.001,
            format="%.4f",
            key=f"{key}_n",
        )
    with col2:
        if allow_flat:
            slope = st.number_input(
                "Bed slope, S₀ (m/m)",
                value=default_slope,
                step=0.0001,
                format="%.6f",
                key=f"{key}_slope",
                help="0 means a horizontal bed; a negative value means an adverse slope.",
            )
        else:
            slope = st.number_input(
                "Bed slope, S₀ (m/m)",
                min_value=0.000001,
                value=default_slope,
                step=0.0001,
                format="%.6f",
                key=f"{key}_slope",
            )
    return n_value, slope


# ----------------------------------------------------------------------
# Tables
# ----------------------------------------------------------------------

def round_rows(rows, digits: int = 4):
    return [
        {k: (round(v, digits) if isinstance(v, float) else v) for k, v in row.items()}
        for row in rows
    ]


def show_table(rows, digits: int = 4) -> None:
    st.dataframe(round_rows(rows, digits), width="stretch", hide_index=True)


def rows_to_dict(rows):
    """[{'Quantity': q, 'Value': v}, ...] -> {q: v, ...}"""
    return {r["Quantity"]: r["Value"] for r in rows}


# ----------------------------------------------------------------------
# Results offered to the PDF report
# ----------------------------------------------------------------------

def describe_channel(channel) -> str:
    kind, p = hx.channel_kind(channel)
    if kind == "rectangular":
        return f"Rectangular, b = {p['b']:g} m"
    if kind == "trapezoidal":
        return (f"Trapezoidal, b = {p['b']:g} m, side slopes "
                f"{p['m1']:g}:1 and {p['m2']:g}:1")
    if kind == "triangular":
        return f"Triangular, side slopes {p['m1']:g}:1 and {p['m2']:g}:1"
    return f"Circular, D = {p['D']:g} m"


def table_payload(rows, title: str, digits: int = 4, max_rows: int = 40):
    """Turn a list of row dictionaries into the table block used by the report."""
    if not rows:
        return None
    if len(rows) > max_rows:
        step = math.ceil(len(rows) / max_rows)
        thinned = rows[::step]
        if thinned[-1] is not rows[-1]:
            thinned.append(rows[-1])
        rows = thinned
    columns = list(rows[0].keys())
    return {
        "title": title,
        "columns": columns,
        "rows": [
            [
                (f"{v:.{digits}f}" if math.isfinite(v) else "—") if isinstance(v, float) else str(v)
                for v in row.values()
            ]
            for row in rows
        ],
    }


def record(key, title, basis, inputs, results, table=None, figure=None, channel=None):
    """Save a finished calculation so it can be added to the PDF report.

    key     identifies the tool; running it again replaces the earlier entry
    basis   one line describing the method or governing equation
    inputs  and results are ordered {label: text} dictionaries
    """
    items = st.session_state.get(REPORT_KEY)
    if items is None:
        items = {}
        st.session_state[REPORT_KEY] = items
    entry = {
        "title": title, "basis": basis,
        "inputs": dict(inputs), "results": dict(results),
    }
    if channel is not None:
        entry["inputs"] = {"Channel": describe_channel(channel), **entry["inputs"]}
    if table:
        entry["table"] = table
    if figure is not None:
        buffer = BytesIO()
        figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
        entry["figure_png"] = buffer.getvalue()
    items[key] = entry


def saved_items() -> dict:
    return st.session_state.get(REPORT_KEY) or {}


def clear_saved_items() -> None:
    st.session_state[REPORT_KEY] = {}
