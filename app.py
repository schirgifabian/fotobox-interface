import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
from datetime import datetime

# --- KONFIGURATION ---
MAX_PRINTS_PER_ROLL = 400  # Maximale Kapazität einer Rolle beim Citizen CX02
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- LOTTIE ANIMATIONEN LADEN ---
def load_lottieurl(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# URLs für Animationen (frei verfügbar von LottieFiles)
lottie_printing = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_yyja09.json") # Ein Drucker oder Zahnrad
lottie_ready = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_jbrw3hcz.json")   # Checkmark
lottie_error = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_Tkwjw8.json")     # Warning

# --- GOOGLE SHEETS VERBINDUNG ---
def get_data():
    # Secrets laden
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    
    # Öffnen (ggf. auf open_by_key ändern, falls du die Drive API nicht aktiviert hast)
    try:
        sh = gc.open("DruckerStatus") # Oder gc.open_by_key("DEINE_ID")
        worksheet = sh.sheet1
        # Alle Daten holen und in Pandas DataFrame wandeln
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Fehler beim Verbinden mit Google Sheets: {e}")
        return pd.DataFrame()

# --- APP LAYOUT ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

st.title(f"{PAGE_ICON} {PAGE_TITLE}")
st.markdown("---")

# Button zum manuellen Aktualisieren
if st.button("🔄 Status aktualisieren"):
    st.rerun()

df = get_data()

if not df.empty:
    # Letzte Zeile holen (neuester Status)
    last_entry = df.iloc[-1]
    
    status = str(last_entry.get("Status", "Unknown"))
    media_remaining = int(last_entry.get("Media_Remaining", 0))
    timestamp = last_entry.get("Timestamp", "-")
    
    # Layout in 2 Spalten: Links Animation, Rechts Infos
    col1, col2 = st.columns([1, 2])

    # --- LOGIK FÜR STATUS & ANIMATION ---
    with col1:
        if "Printing" in status:
            st_lottie(lottie_printing, height=200, key="printing")
            status_color = "orange"
            status_text = "Druckt gerade..."
        elif "Ready" in status or "Bereit" in status:
            st_lottie(lottie_ready, height=200, key="ready")
            status_color = "green"
            status_text = "Drucker bereit"
        else:
            st_lottie(lottie_error, height=200, key="error")
            status_color = "red"
            status_text = f"Fehler / Status: {status}"

    with col2:
        # Große Anzeige des Status
        st.markdown(f"<h2 style='color:{status_color};'>{status_text}</h2>", unsafe_allow_html=True)
        
        st.write(f"🕒 Letztes Update: **{timestamp}**")
        
        # Metrik Anzeige für verbleibende Bilder
        st.metric(label="Verbleibende Bilder", value=f"{media_remaining} Stk", delta=None)

        # Fortschrittsbalken für Papier
        # Berechnung Prozent: (Verbleibend / Max) 
        # Schutz vor Division durch Null oder Werten über 100%
        progress_val = max(0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
        
        st.write("Papierstatus:")
        if progress_val < 0.1:
            st.progress(progress_val, text="⚠️ Papier fast leer!")
        else:
            st.progress(progress_val)

    # --- HISTORIE (Optional unten anzeigen) ---
    with st.expander("📜 Verlauf anzeigen (Letzte 5 Einträge)"):
        st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)

else:
    st.info("Warte auf Daten vom Drucker...")
