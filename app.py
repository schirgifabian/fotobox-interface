import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
from streamlit_autorefresh import st_autorefresh # Wichtig für automatische Updates

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
MAX_PRINTS_PER_ROLL = 400
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"
REFRESH_INTERVAL = 10000  # 10 Sekunden

# --- SEITEN KONFIGURATION (Muss ganz oben stehen) ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- AUTO-REFRESH ---
# Aktualisiert die Seite automatisch alle 10 Sekunden
st_autorefresh(interval=REFRESH_INTERVAL, limit=None, key="fotorrefresh")

# --- CACHING & LOTTIE ---
@st.cache_data(ttl=3600) # Lotties für 1 Stunde cachen
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

lottie_printing = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_yyja09.json")
lottie_ready = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_jbrw3hcz.json")
lottie_error = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_Tkwjw8.json")

# --- GOOGLE SHEETS VERBINDUNG ---
# Cache für 10 Sekunden, damit wir nicht bei jedem Klick die API belasten
@st.cache_data(ttl=10) 
def get_data():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    try:
        creds = Credentials.from_service_account_info(secrets, scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        return pd.DataFrame() # Leeres DataFrame bei Fehler

# --- APP LOGIK & DESIGN ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")
st.markdown("---")

# Manueller Button (zusätzlich zum Auto-Refresh)
if st.button("🔄 Sofort aktualisieren"):
    st.cache_data.clear() # Cache löschen für sofortige frische Daten
    st.rerun()

df = get_data()

if not df.empty:
    try:
        last_entry = df.iloc[-1]
        
        status = str(last_entry.get("Status", "Unknown"))
        
        try:
            media_remaining = int(last_entry.get("Media_Remaining", 0))
        except ValueError:
            media_remaining = 0
            
        timestamp = last_entry.get("Timestamp", "-")
        
        # --- DEIN URSPRÜNGLICHES LAYOUT (1:2 Spalten) ---
        col1, col2 = st.columns([1, 2])

        with col1:
            # Die Animationen passend zum Status
            if "Printing" in status:
                st_lottie(lottie_printing, height=200, key="printing")
                status_color = "orange"
                status_text = "Druckt gerade..."
            elif "Ready" in status or "Bereit" in status:
                st_lottie(lottie_ready, height=200, key="ready")
                status_color = "green"
                status_text = "Drucker bereit"
            else:
                # Alles andere ist ein Fehler (Papierstau etc.)
                st_lottie(lottie_error, height=200, key="error")
                status_color = "red"
                status_text = f"Status: {status}"

        with col2:
            # Text und Balken
            st.markdown(f"<h2 style='color:{status_color};'>{status_text}</h2>", unsafe_allow_html=True)
            st.write(f"🕒 Letztes Update: **{timestamp}**")
            st.metric(label="Verbleibende Bilder", value=f"{media_remaining} Stk")

            progress_val = max(0.0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
            st.write("Papierstatus:")
            
            if progress_val < 0.1:
                st.progress(progress_val, text="⚠️ Papier fast leer!")
            else:
                st.progress(progress_val)

        # Verlauf unten drunter
        with st.expander("📜 Verlauf anzeigen"):
            st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)
            
    except Exception as e:
        st.error(f"Fehler beim Verarbeiten der Daten: {e}")
else:
    st.info("Warte auf Datenverbindung...")
    st.spinner("Lade...")
