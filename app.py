import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
import time

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
MAX_PRINTS_PER_ROLL = 400
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# Initialisiere Session State für den Reset-Dialog
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

# --- CACHING & LOTTIE ---
@st.cache_data(ttl=3600)
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

# --- GOOGLE SHEETS HELPER ---
def get_worksheet():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.sheet1

# --- DATEN LADEN (MIT CACHE) ---
@st.cache_data(ttl=0)
def get_data():
    try:
        worksheet = get_worksheet()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        return pd.DataFrame()

# --- DATEN LÖSCHEN FUNKTION ---
def clear_google_sheet():
    try:
        ws = get_worksheet()
        ws.batch_clear(["A2:Z10000"]) # Löscht Inhalt, behält Header
        st.toast("Log erfolgreich geleert!", icon="✅")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fehler beim Löschen: {e}")

# --- LAYOUT START ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")
st.markdown("---")

# --- LIVE FRAGMENT (Aktualisiert alle 10s, aber ohne Flackern) ---
@st.fragment(run_every=10)
def show_live_status():
    # Button zum manuellen Neuladen (nur Daten)
    if st.button("🔄 Status prüfen", key="refresh_fragment"):
        st.cache_data.clear()
    
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
            
            # Spaltenaufteilung
            col1, col2 = st.columns([1, 2])

            # Logik für Animation und Text bestimmen
            if "Printing" in status:
                current_lottie = lottie_printing
                status_color = "orange"
                status_text = "Druckt gerade..."
            elif "Ready" in status or "Bereit" in status:
                current_lottie = lottie_ready
                status_color = "green"
                status_text = "Drucker bereit"
            else:
                current_lottie = lottie_error
                status_color = "red"
                status_text = f"Status: {status}"

            with col1:
                # WICHTIG: key="status_animation" bleibt immer gleich. 
                # Dadurch lädt Streamlit das Lottie NICHT neu, solange sich 'current_lottie' nicht ändert.
                st_lottie(current_lottie, height=200, key="status_animation")

            with col2:
                st.markdown(f"<h2 style='color:{status_color};'>{status_text}</h2>", unsafe_allow_html=True)
                st.write(f"🕒 Letztes Update: **{timestamp}**")
                st.metric(label="Verbleibende Bilder", value=f"{media_remaining} Stk")

                progress_val = max(0.0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
                st.write("Papierstatus:")
                if progress_val < 0.1:
                    st.progress(progress_val, text="⚠️ Papier fast leer!")
                else:
                    st.progress(progress_val)

            with st.expander("📜 Verlauf anzeigen"):
                st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)
                
        except Exception as e:
            st.error(f"Fehler in der Datenverarbeitung: {e}")
    else:
        st.info("Keine Daten vorhanden oder Datenbank leer.")

# Fragment starten
show_live_status()

st.markdown("---")

# --- ADMIN TOOLS (Stabil, lädt nicht automatisch neu) ---
with st.expander("🛠️ Admin & Einstellungen", expanded=True):
    
    col_admin1, col_admin2 = st.columns(2)
    
    with col_admin1:
        st.link_button("🔗 Zu Fotoshare Admin", "https://fotoshare.co/admin/index", use_container_width=True)
    
    with col_admin2:
        # Reset Logik mit Bestätigung
        if not st.session_state.confirm_reset:
            if st.button("🗑️ Log Datei leeren", use_container_width=True):
                st.session_state.confirm_reset = True
                st.rerun()
        else:
            st.warning("⚠️ Wirklich löschen?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Ja", use_container_width=True):
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.rerun()
            
            if col_no.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
