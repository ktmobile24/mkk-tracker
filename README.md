# MKK Investment Tracker — Web (Streamlit)

This package is ready to deploy your **original Streamlit app** as a shareable website (same look & behavior).

## 1) Run locally
```bash
pip install -r requirements.txt
streamlit run tracker_app.py
```

Your data reads/writes to `portfolio_data.json` in the same folder.

## 2) Deploy to Streamlit Community Cloud (recommended, free)
1. Create a **public GitHub repo** and upload these files at the repo root:
   - `tracker_app.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `portfolio_data.json` (optional, to preload)
   - `icon.png` (optional)
2. Go to https://streamlit.io/cloud → **New app**
3. Select your repo and set **Main file** to `tracker_app.py`
4. Click **Deploy**

You’ll get a shareable URL like `https://<your-app-name>-<user>.streamlit.app`.

> **Note on saving data:** Streamlit Cloud’s filesystem is ephemeral. Use **Export** inside your app (if available), or add a small backend (Google Sheets, Supabase, GitHub write-back). I can wire this up if you want persistent storage.

## 3) Optional: Hugging Face Spaces (also free)
1. Sign in at https://huggingface.co/
2. Create a new **Space** → **Streamlit** template
3. Upload the same files; set `tracker_app.py` as the entry point

## 4) (If you *must* have an `index.html` to share)
Create a simple landing page that points to your Streamlit URL. Replace `YOUR_STREAMLIT_URL` below, then host this on GitHub Pages/Netlify:

```html
<!doctype html><meta charset="utf-8">
<title>MKK Tracker</title>
<style>body{margin:0;height:100vh}iframe{border:0;width:100%;height:100%}</style>
<iframe src="YOUR_STREAMLIT_URL" allow="clipboard-write *"></iframe>
```

That gives you a classic `index.html` address while the app actually runs on Streamlit behind the scenes.
