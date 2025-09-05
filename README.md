# MKK Investment Tracker — Streamlit (Auto-Bootstrap)
This version adds a small bootstrap that installs packages at runtime if Streamlit Cloud missed them.

## Deploy
1) Upload these files to a **public** GitHub repo (root):
   - `tracker_app.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `portfolio_data.json` (optional)
2) On Streamlit Cloud: New app → Main file: `tracker_app.py` → Deploy.
