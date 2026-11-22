# Open Channel Flow Calculator

A responsive browser-based interface for the existing Python open-channel calculation engine.

## Features
- Rectangular, trapezoidal, triangular and circular channel sections
- Section geometry
- Manning discharge, velocity and normal depth
- Critical depth, specific energy, Froude number and flow regime
- Discharge-depth curve and sampled values

## Run in VS Code

1. Extract this folder and open it in VS Code.
2. Open the integrated terminal in this folder.
3. Create and activate a virtual environment (recommended):

   Windows:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Start the web application:
   ```powershell
   streamlit run app.py
   ```

6. Streamlit will print a local URL, normally `http://localhost:8501`. Open it in your browser.

## Notes
- `open_channel_program_fixed.py` contains the calculation classes and methods.
- `app.py` is the Streamlit user interface and imports the existing calculation engine.
- The desktop GUI can be added later using the same calculation module.
- This is an engineering calculation aid. Independently verify design assumptions and results before construction use.
