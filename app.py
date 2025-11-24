import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
import time
from datetime import datetime, timedelta

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
MAX_PRINTS_PER_ROLL = 400
WARNING_THRESHOLD = 20
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- NTFY EINSTELLUNGEN ---
NTFY_TOPIC = "fotobox_status_secret_4566"
NTFY_ACTIVE_DEFAULT = True

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE INITIALISIERUNG ---
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "low_paper_warned" not in st.session_state:
    st.session_state.low_paper_warned = False

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200: return None
        return r.json()
    except: return None

# Animationen
lottie_printing = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_yyja09.json")
lottie_warning = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_2ycju1.json")
lottie_ok = load_lottieurl("https://assets.lottiefiles.com/packages/lf20_jbrw3hcz.json")

def get_data():
    """Lädt Daten aus Google Sheets"""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Zeitstempel in echtes Datum umwandeln
    if not df.empty and 'Time' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
    return df

def clear_google_sheet():
    """Setzt das Google Sheet zurück"""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    sheet.clear()
    sheet.append_row(["Time", "Status", "Media_Remaining"])
    st.session_state.low_paper_warned = False # Warnstatus zurücksetzen

def send_ntfy_push(title, message, tags="warning", priority=3):
    """Sendet Push via ntfy.sh"""
    if not st.session_state.ntfy_active:
        return False
    
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    try:
        # Kodierung als utf-8 für Emojis
        requests.post(
            url,
            data=message.encode(encoding='utf-8'),
            headers={
                "Title": title,
                "Priority": str(priority),
                "Tags": tags,
            },
            timeout=5
        )
        return True
    except Exception as e:
        print(f"NTFY Fehler: {e}")
        return False

def calculate_forecast(df, remaining_prints):
    """Berechnet Restlaufzeit basierend auf den letzten 60 Minuten"""
    if df.empty or 'Time' not in df.columns:
        return "Keine Daten"
    
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    # Zähle Drucke der letzten Stunde
    recent_prints = df[df['Time'] > one_hour_ago]
    prints_per_hour = len(recent_prints)
    
    if prints_per_hour < 2:
        return "Warte auf Drucke..."
    
    hours_left = remaining_prints / prints_per_hour
    
    if hours_left > 24:
        return "> 24 Std."
    
    h = int(hours_left)
    m = int((hours_left - h) * 60)
    return f"ca. {h} Std. {m} Min."

# --- MAIN DASHBOARD (LIVE REFRESH) ---
@st.fragment(run_every=10)
def show_live_status():
    st.title("📸 Fotobox Status")
    
    df = get_data()
    
    # Berechnung
    prints_done = len(df)
    prints_remaining = MAX_PRINTS_PER_ROLL - prints_done
    
    # Prozent für Progress Bar
    progress_value = max(0.0, min(1.0, prints_remaining / MAX_PRINTS_PER_ROLL))
    
    # Prognose
    forecast_text = calculate_forecast(df, prints_remaining)

    # --- ANZEIGE ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Verbleibend", f"{prints_remaining}", f"Max: {MAX_PRINTS_PER_ROLL}")
    col2.metric("Gedruckt", f"{prints_done}")
    col3.metric("Laufzeit-Prognose", forecast_text)

    st.progress(progress_value)

    # Status Logik & Animation
    if prints_remaining <= 0:
        st.error("⚠️ PAPIER LEER! Bitte wechseln.")
        st_lottie(lottie_warning, height=200, key="anim_empty")
    elif prints_remaining <= WARNING_THRESHOLD:
        st.warning(f"⚠️ Papier fast leer (<{WARNING_THRESHOLD})")
        st_lottie(lottie_warning, height=200, key="anim_warn")
        
        # Push Senden (nur einmal)
        if not st.session_state.low_paper_warned:
            sent = send_ntfy_push(
                "⚠️ Papier kritisch!",
                f"Nur noch {prints_remaining} Bilder übrig! Bitte Rolle bereitlegen.",
                tags="rotating_light",
                priority=4
            )
            if sent:
                st.session_state.low_paper_warned = True
                
    else:
        st.success("System läuft normal")
        st_lottie(lottie_printing, height=200, key="anim_ok")

    # Letzte Aktivität
    if not df.empty:
        last_time = df.iloc[-1]['Time']
        st.caption(f"Letzter Druck: {last_time}")

# --- APP START ---

show_live_status()

st.divider()

# --- ADMIN BEREICH ---
with st.expander("⚙️ Admin & Einstellungen"):
    st.write("### Benachrichtigungen")
    st.info(f"Sende an Topic: `{NTFY_TOPIC}`")
    
    st.session_state.ntfy_active = st.checkbox("Push-Nachrichten aktivieren", value=st.session_state.ntfy_active)
    
    if st.button("Test-Nachricht senden 🚀"):
        success = send_ntfy_push("Test", "Dies ist ein Test vom Dashboard! 📱", tags="tada")
        if success:
            st.toast("Nachricht gesendet!", icon="✅")
        else:
            st.error("Fehler beim Senden.")

    st.write("### Wartung")
    if st.button("Papierwechsel durchgeführt (Reset) 🔄"):
        clear_google_sheet()
        st.rerun()
