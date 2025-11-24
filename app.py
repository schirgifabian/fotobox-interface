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
    """Lädt Lottie Animationen sicher"""
    try:
        r = requests.get(url, timeout=3)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

# Animationen laden (mit Fallback, falls Server down ist)
lottie_printing = load_lottieurl("https://lottie.host/5a8439d0-a686-40df-996c-7234f2903e25/6F0s8Y5s2R.json") # Neuer Working Link
lottie_warning = load_lottieurl("https://lottie.host/9415257e-28c4-4a76-af37-0418586e45e6/uX5Kz8q7sJ.json") # Neuer Working Link

def get_data():
    """Lädt Daten aus Google Sheets"""
    try:
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
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        return pd.DataFrame()

def clear_google_sheet():
    """Setzt das Google Sheet zurück (leert alles außer Header)"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        # Alle Zeilen ab Zeile 2 löschen
        sheet.resize(rows=1)
        sheet.resize(rows=1000) # Wieder Platz schaffen
        
        # Reset Session States
        st.session_state.low_paper_warned = False
        return True
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")
        return False

def send_ntfy_push(title, message, tags="warning", priority=3):
    """Sendet Push via ntfy.sh (mit UTF-8 Encoding Fix)"""
    if not st.session_state.ntfy_active:
        return False
    
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'), # Wichtig für Emojis und Umlaute
            headers={
                "Title": title.encode('utf-8'), # Header auch encoden, sicher ist sicher
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
    """Berechnet die geschätzte Restlaufzeit basierend auf der letzten Stunde"""
    if df.empty or 'Time' not in df.columns:
        return "Keine Daten"
    
    # Filtere Einträge der letzten 60 Minuten
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    # Nur gültige Zeitstempel nutzen
    recent_prints = df[df['Time'] > one_hour_ago]
    prints_last_hour = len(recent_prints)
    
    if prints_last_hour < 2:
        return "Warte auf mehr Drucke..."
    
    # Berechnung: Wenn es so weitergeht wie in der letzten Stunde...
    if prints_last_hour > 0:
        hours_left = remaining_prints / prints_last_hour
    else:
        return "∞"

    if hours_left > 24:
        return "> 24 Stunden"
    
    # Stunden und Minuten extrahieren
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

    # Status Logik & Animation (JETZT ABSTURZSICHER)
    if prints_remaining <= 0:
        st.error("⚠️ PAPIER LEER! Bitte wechseln.")
        if lottie_warning:
            st_lottie(lottie_warning, height=200, key="anim_empty")
    
    elif prints_remaining <= WARNING_THRESHOLD:
        st.warning(f"⚠️ Papier fast leer (<{WARNING_THRESHOLD})")
        if lottie_warning:
            st_lottie(lottie_warning, height=200, key="anim_warn")
        else:
            st.markdown("⚠️⚠️⚠️") # Fallback Emoji
        
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
        if lottie_printing:
            st_lottie(lottie_printing, height=200, key="anim_ok")
        else:
            st.markdown("✅") # Fallback Emoji

    # Letzte Aktivität
    if not df.empty:
        try:
            last_time = df.iloc[-1]['Time']
            st.caption(f"Letzter Druck: {last_time}")
        except:
            pass

# --- APP START ---

show_live_status()

st.divider()

# --- ADMIN BEREICH ---
with st.expander("⚙️ Admin & Einstellungen"):
    st.write("### Benachrichtigungen")
    st.info(f"Sende an Topic: `{NTFY_TOPIC}`")
    
    st.session_state.ntfy_active = st.checkbox("Push-Nachrichten aktivieren", value=st.session_state.ntfy_active)
    
    if st.button("Test-Nachricht senden 🚀"):
        # Testet die Encoding Funktion
        success = send_ntfy_push("Test 🧪", "Dies ist ein Test vom Dashboard! Funktioniert ntfy? 📱", tags="tada")
        if success:
            st.toast("Nachricht gesendet!", icon="✅")
        else:
            st.error("Fehler beim Senden.")

    st.write("### Wartung")
    if st.button("Papierwechsel durchgeführt (Reset) 🔄"):
        if clear_google_sheet():
            st.success("Zähler zurückgesetzt!")
            time.sleep(1)
            st.rerun()
