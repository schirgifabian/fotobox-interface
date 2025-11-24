import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
from datetime import datetime

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
MAX_PRINTS_PER_ROLL = 400
PAGE_TITLE = "Drucker Monitor"
PAGE_ICON = "🖨️"
REFRESH_RATE = 10

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- CUSTOM CSS FÜR SCHÖNEREN LOOK ---
st.markdown("""
    <style>
        /* Etwas Platz oben entfernen */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        /* Metrik-Label stylen */
        div[data-testid="stMetricLabel"] {
            font-size: 1.1rem !important;
        }
        /* Metrik-Wert größer machen */
        div[data-testid="stMetricValue"] {
            font-size: 2.5rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- LOTTIE LADEN ---
@st.cache_data
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Animationen
lottie_printing = load_lottieurl("https://lottie.host/55b00152-04f4-486a-b39d-229421c2136c/c8lq8p6KqY.json") # Drucker Animation
lottie_ready = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_jbrw3hcz.json") # Checkmark
lottie_error = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_qpwbv5gm.json") # Warnung

# --- GOOGLE SHEETS VERBINDUNG ---
@st.cache_resource
def get_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# --- HAUPT-APP (AUTO-REFRESH) ---
@st.fragment(run_every=REFRESH_RATE)
def show_status_monitor():
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    
    try:
        gc = get_connection()
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
        data = worksheet.get_all_records()
        
        if not data:
            st.info("Verbindung erfolgreich, warte auf erste Daten...")
            return

        df = pd.DataFrame(data)
        last_entry = df.iloc[-1]
        
        # Daten auslesen
        status_raw = str(last_entry.get("Status", "Unbekannt"))
        try:
            media_remaining = int(last_entry.get("Media_Remaining", 0))
        except:
            media_remaining = 0
        timestamp = last_entry.get("Timestamp", "-")

        # --- LOGIK FÜR STATUS ---
        # Standardwerte
        lottie_to_show = lottie_error
        status_color = "#FF4B4B" # Rot
        status_display_text = f"⚠ {status_raw}"
        
        if "Printing" in status_raw:
            lottie_to_show = lottie_printing
            status_color = "#FFA500" # Orange
            status_display_text = "Druckt..."
            
        elif "Ready" in status_raw or "Bereit" in status_raw or "OK" in status_raw:
            lottie_to_show = lottie_ready
            status_color = "#09AB3B" # Grün
            status_display_text = "Bereit"

        # --- DARSTELLUNG ---
        
        # Wir packen alles in einen Container mit Rahmen (sieht aus wie eine Karte)
        with st.container(border=True):
            
            # Spalten: Links Bild, Rechts Text.
            # vertical_alignment="center" sorgt dafür, dass Text mittig zum Bild steht!
            col_anim, col_info = st.columns([1, 1.5], gap="large", vertical_alignment="center")
            
            with col_anim:
                if lottie_to_show:
                    st_lottie(lottie_to_show, height=180, key=f"anim_{timestamp}")
                else:
                    st.write("🎞") # Platzhalter falls Lottie fehlschlägt

            with col_info:
                # Status Titel in Farbe
                st.markdown(f"""
                    <h1 style='color: {status_color}; margin:0; padding:0; font-size: 2.8rem;'>
                        {status_display_text}
                    </h1>
                    """, unsafe_allow_html=True)
                
                st.markdown(f"<p style='color:gray; margin-top: -10px;'>Letztes Update: {timestamp}</p>", unsafe_allow_html=True)

        # --- FORTSCHRITTSBALKEN & DETAILS ---
        st.write("") # Abstand
        
        col_metric, col_bar = st.columns([1, 2], vertical_alignment="bottom")
        
        with col_metric:
            st.metric(label="Verbleibende Bilder", value=f"{media_remaining}")
            
        with col_bar:
            progress_val = max(0.0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
            
            # Farbe des Balkens je nach Füllstand simulieren (Text darüber)
            if progress_val < 0.1:
                st.markdown("<b style='color:red'>Papier fast leer! ⚠️</b>", unsafe_allow_html=True)
            else:
                st.write("<b>Papierrolle Status</b>", unsafe_allow_html=True)
                
            st.progress(progress_val)

        # --- VERLAUF (Eingeklappt) ---
        st.divider()
        with st.expander("Logbuch anzeigen"):
            st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Verbindungsfehler: {e}")

# Start
if __name__ == "__main__":
    show_status_monitor()
