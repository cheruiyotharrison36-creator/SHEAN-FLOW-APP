# SHEAN FLOW APP

Open-channel hydraulics calculator for rectangular, trapezoidal, triangular and
circular sections. It runs in any web browser on a computer or a phone.

## What it does

| Tab | Calculations |
|---|---|
| Section geometry | Flow area, wetted perimeter, top width, hydraulic radius, hydraulic depth, cross-section diagram |
| Manning flow | Discharge and velocity from depth; normal depth from discharge, with a trial-and-error table |
| Uniform flow tools | Solve the Chezy–Manning equation for Q, y₀, n, S₀ or bottom width; Froude and Reynolds numbers, wall shear stress, Chezy C; partly full pipes; most efficient sections |
| Critical flow | Critical depth, specific energy, Froude number and flow regime |
| Specific energy | Energy–depth curve; alternate depth by bisection, Newton–Raphson or trial and error; bed steps and choking; width changes; reservoir entrance; transition losses |
| Hydraulic jump | Sequent depth in any section, rectangular jump from the Froude number, head loss, power, jump type and length, baffle blocks, moving surge, force on a gate |
| Gradually varied flow | Slope class (M, S, C, H, A), profile name, direct step method, Runge–Kutta integration, sluice gate with M3 profile and jump |
| Weirs and flumes | Broad-crested, rectangular sharp-crested (Rehbock or Kindsvater–Carter), V-notch, Francis and Parshall flume, each for discharge from head and head from discharge |
| Discharge-depth curve | Discharge, velocity, area and Froude number against depth |
| PDF Engineering Report | Project report with the section, diagram, results and any calculation saved from the other tabs |

Units are metres, m³/s and m/m (bed slope). Manning's n is dimensionless.

## Run it

    pip install -r requirements.txt
    python -m streamlit run app.py

## Project structure

    app.py               page layout, sidebar and the core tabs
    ui_tabs.py           screens for the additional tabs
    ui_common.py         shared widgets, formatting and the report store
    open_channel.py      channel classes, Manning, critical flow, hydraulic jump
    hydraulic_tools.py   uniform-flow solver, energy, transitions, weirs, GVF, rating table
    channel_diagrams.py  cross-section drawings
    pdf_report.py        PDF report builder
    test_verification.py benchmark checks (python test_verification.py)

## Verification

`test_verification.py` compares the software with hand calculations and
benchmark cases (geometry, Manning flow, critical flow, hydraulic jumps,
transitions, weirs and gradually varied flow). Every check must pass.

## Limits of use

This is an engineering calculation aid. Weir and flume coefficients,
empirical jump lengths and roughness values are approximate and depend on
site conditions. Verify results independently before using them in design.

## References

- Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill.
- Henderson, F. M. (1966). *Open Channel Flow*. Macmillan.
- French, R. H. (1985). *Open-Channel Hydraulics*. McGraw-Hill.
- Chaudhry, M. H. (2008). *Open-Channel Flow*. Springer.
- Sturm, T. W. (2010). *Open Channel Hydraulics*. McGraw-Hill.
- Subramanya, K. (2015). *Flow in Open Channels*. McGraw-Hill.
- Bakhmeteff, B. A. and Matzke, A. E. (1936). The hydraulic jump in terms of dynamic similarity. *Transactions of the ASCE*.
- Kindsvater, C. E. and Carter, R. W. (1959). Discharge characteristics of rectangular thin-plate weirs. *Transactions of the ASCE*.
- Rehbock, T. (1929). Discharge coefficient of sharp-crested weirs.
- U.S. Bureau of Reclamation. *Water Measurement Manual*.
