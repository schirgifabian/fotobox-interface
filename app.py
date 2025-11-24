import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
from datetime import datetime

# --- KONFIGURATION ---
# Deine Google Sheet ID ist jetzt hier fest eingetragen:
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"

MAX_PRINTS_PER_ROLL = 400
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"
REFRESH_RATE = 10  # Aktualisierung alle 10 Sekunden

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON)

# --- LOTTIE ANIMATIONEN LADEN ---
@st.cache_data
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
lottie_error = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_qpwbv5gm.json")

# --- GOOGLE SHEETS VERBINDUNG ---
@st.cache_resource
def get_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    # Secrets werden aus der Streamlit Cloud geladen
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

# --- HAUPT-APP MIT AUTO-REFRESH ---
# Diese Funktion führt sich selbst alle 10 Sekunden neu aus
@st.fragment(run_every=REFRESH_RATE)
def show_status_monitor():
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    
    try:
        # Verbindung holen
        gc = get_connection()
        
        # Versuchen das Sheet mit deiner ID zu öffnen
        try:
            sh = gc.open_by_key(SHEET_ID)
            worksheet = sh.sheet1
        except Exception as e:
            st.error(f"⚠ Fehler: Zugriff verweigert oder falsche ID.\n\nBitte prüfe: Hast du das Google Sheet mit der 'client_email' aus deinen Secrets geteilt?\n\nDetails: {e}")
            return

        # Daten laden
        data = worksheet.get_all_records()
        
        if not data:
            st.warning("Verbindung steht, aber die Tabelle ist noch leer. Warte auf Daten...")
            st.caption(f"Letzter Check: {datetime.now().strftime('%H:%M:%S')}")
            return

        df = pd.DataFrame(data)
        
        # Letzte Zeile holen
        last_entry = df.iloc[-1]
        status = str(last_entry.get("Status", "Unbekannt"))
        
        # Sicherstellen, dass Media_Remaining eine Zahl ist
        try:
            media_remaining = int(last_entry.get("Media_Remaining", 0))
        except ValueError:
            media_remaining = 0
            
        timestamp = last_entry.get("Timestamp", "-")
        
        # Layout erstellen
        col1, col2 = st.columns([1, 2])

        with col1:
            # Status Logik
            if "Printing" in status:
                if lottie_printing:
                    st_lottie(lottie_printing, height=200, key=f"p_{timestamp}")
                status_color = "orange"
                status_text = "Druckt gerade..."
                
            elif "Ready" in status or "Bereit" in status or "OK" in status:
                if lottie_ready:
                    st_lottie(lottie_ready, height=200, key=f"r_{timestamp}")
                status_color = "green"
                status_text = "Drucker bereit"
                
            else:
                # Fehlerfall (z.B. Papierstau)
                if lottie_error:
                    st_lottie(lottie_error, height=200, key=f"e_{timestamp}")
                status_color = "red"
                status_text = f"⚠ {status}"

        with col2:
            # Status Text
            st.markdown(f"<h1 style='color:{status_color}; margin-bottom:0;'>{status_text}</h1>", unsafe_allow_html=True)
            st.write(f"🕒 Letztes Update: **{timestamp}**")
            
            # Bilder Zähler
            st.metric(label="Verbleibende Bilder", value=f"{media_remaining} Stk")

            # Fortschrittsbalken
            progress_val = max(0.0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
            st.write("Papierrolle:")
            
            if progress_val < 0.1:
                st.warning("⚠️ Papier fast leer! Bitte wechseln.")
            
            st.progress(progress_val)

        # Debug / Verlauf (optional)
        with st.expander("Verlauf ansehen"):
            st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)
            
        st.caption(f"Live-Monitor aktiv • Aktualisiert alle {REFRESH_RATE}s automatisch.")

    except Exception as e:
        st.error(f"Allgemeiner Fehler: {e}")

# --- APP STARTEN ---
if __name__ == "__main__":
    show_status_monitor()
